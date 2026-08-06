"""The serving entry point: configuration, logging, then one loaded artifact (T-006).

This is the only module that reads the process environment to decide how to run, and
it is deliberately thin. `predictor.py` already knows how to verify and load a sealed
bundle and `api.py` already owns the HTTP contract, so the job here is just to resolve
settings, configure logging before anything can log, and hand off.

Two things are worth stating because they are easy to get wrong:

**Loading happens before the port is bound.** `build_app` constructs the predictor
eagerly, so an invalid or missing artifact raises here and `uvicorn` never starts
listening. `ARCHITECTURE.md:110` requires that a corrupt artifact make startup fail
rather than produce a server whose `/health` answers not-ready forever — a listening
process that can never serve is harder to diagnose than one that refused to start.

**Serving never trains, downloads, or selects a threshold.** Nothing in this module or
its imports can fit a model or choose a threshold: it calls `load_artifact_predictor`,
which reads the persisted value. The artifact is opened read-only and the process has
no code path that would write to it.

`INTENTGUARD_HOST`, `INTENTGUARD_PORT`, `INTENTGUARD_LOG_LEVEL`, and
`INTENTGUARD_ARTIFACT_ROOT` are the variables already declared in `.env.example`; this
module is what makes them real rather than aspirational.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import uvicorn
from fastapi import FastAPI

from intentguard.api import create_app, set_predictor
from intentguard.config import load_foundation_config
from intentguard.logging import (
    ARTIFACT_LOADED,
    SERVICE_START,
    PredictionEvent,
    configure_logging,
    log_event,
)
from intentguard.predictor import load_artifact_predictor, resolve_artifact_root

HOST_VARIABLE: Final = "INTENTGUARD_HOST"
PORT_VARIABLE: Final = "INTENTGUARD_PORT"
LOG_LEVEL_VARIABLE: Final = "INTENTGUARD_LOG_LEVEL"

#: Loopback by default. A weekend MVP that bound `0.0.0.0` would expose an
#: unauthenticated classifier to the local network the first time someone ran it, and
#: `INTERFACE_CONTRACT.md:136` documents `127.0.0.1` as the address to call.
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8000
DEFAULT_LOG_LEVEL: Final = "INFO"

#: The configuration file is repository-relative, resolved from this module rather
#: than from the working directory, so `make serve` behaves the same from any cwd.
CONFIG_PATH: Final = Path(__file__).resolve().parents[2] / "configs" / "default.toml"

#: A synthetic correlation ID for the two lifecycle events. `PredictionEvent` requires
#: one, and startup has no request to borrow it from.
STARTUP_REQUEST_ID: Final = "startup"


class ServingError(ValueError):
    """Raised when the environment does not describe a runnable service."""


@dataclass(frozen=True, slots=True)
class ServingSettings:
    """Where to listen and how loudly to log."""

    host: str
    port: int
    log_level: str


def resolve_serving_settings(environ: Mapping[str, str] | None = None) -> ServingSettings:
    """Resolve listening settings from the environment, falling back to the defaults.

    Taking `environ` as a parameter keeps this testable without mutating process
    state. Blank values are treated as unset throughout, because a shell that exports
    a variable without a value should get the default rather than an empty host or a
    `ValueError` from `int("")`.
    """

    source = os.environ if environ is None else environ

    host = source.get(HOST_VARIABLE, "").strip() or DEFAULT_HOST
    log_level = source.get(LOG_LEVEL_VARIABLE, "").strip() or DEFAULT_LOG_LEVEL

    raw_port = source.get(PORT_VARIABLE, "").strip()
    if not raw_port:
        port = DEFAULT_PORT
    else:
        try:
            port = int(raw_port)
        except ValueError as error:
            raise ServingError(f"{PORT_VARIABLE} must be an integer, got {raw_port!r}") from error
    # Port 0 would bind an arbitrary free port, which is useful for a test but wrong
    # for a documented service address: the operator would have no way to know where
    # it landed. The demo picks its own free port explicitly instead.
    if not 1 <= port <= 65535:
        raise ServingError(f"{PORT_VARIABLE} must be between 1 and 65535, got {port}")

    return ServingSettings(host=host, port=port, log_level=log_level)


def build_app(environ: Mapping[str, str] | None = None) -> FastAPI:
    """Configure logging, load the sealed artifact, and return the ready application.

    Usable as a `uvicorn --factory` target. Logging is configured first so the
    artifact-load failure path is itself logged through the service logger rather than
    landing on whatever handler happened to exist.
    """

    settings = resolve_serving_settings(environ)
    configure_logging(settings.log_level)

    config = load_foundation_config(CONFIG_PATH)
    root = resolve_artifact_root(config, environ)
    log_event(
        PredictionEvent(
            event=SERVICE_START,
            request_id=STARTUP_REQUEST_ID,
            input_characters=0,
        )
    )

    predictor = load_artifact_predictor(config, artifact_root=root, environ=environ)
    # Logged after the load rather than around it, so this line can only appear for an
    # artifact that actually passed every checksum and contract check.
    log_event(
        PredictionEvent(
            event=ARTIFACT_LOADED,
            request_id=STARTUP_REQUEST_ID,
            input_characters=0,
            model_version=predictor.model_version,
        )
    )

    app = create_app()
    set_predictor(app, predictor)
    return app


def main() -> None:
    """Serve the loaded artifact until interrupted."""

    settings = resolve_serving_settings()
    app = build_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
