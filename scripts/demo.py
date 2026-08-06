"""The strict real-artifact demonstration (AC-013).

Starts the real service in a child process, waits for `/health` to report ready, then
sends two requests over HTTP: one plainly in-domain, and the abstention fixture row
`unsupported-001`. Everything the transcript claims is read back from the wire.

Three decisions shape this script:

**It talks HTTP to a subprocess, not to a `TestClient`.** A test client calls the ASGI
application in-process, which would prove the predictor works but not that `make serve`
produces a service anyone can reach. AC-013 is about the deployed path, so the demo
pays for a real socket and a real Uvicorn.

**The abstained request is the measured fixture row, not a guess.** `unsupported-001`
("the Lisbon question") abstained at confidence 0.0413 against the persisted threshold
0.1684 in the E05 evaluation, a margin of four times the threshold. Picking a text and
hoping it abstains would make the demo a coin flip on the model's behaviour;
`INTERFACE_CONTRACT.md:153-156` asks specifically for a known low-confidence example.
The fixture file is read for the text rather than hardcoding it, so the demo and the
evaluation cannot drift apart silently.

**Shutdown is guaranteed, then verified.** The child is terminated in a `finally`
block, escalated to `kill` if it ignores `SIGTERM`, and waited for — a demo that
leaves a process holding port 8000 would break the next run in a way that looks like a
different bug. The port is chosen by binding an ephemeral one and releasing it, so a
service the operator is already running is never disturbed.

The demo asserts the decisions it was designed to show, and exits non-zero if either
fails. It reports the confidences it observed but asserts no particular value: those
belong to the weights, and pinning one here would convert a measurement into a
fixture.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
FIXTURE_PATH: Final = REPOSITORY_ROOT / "tests" / "fixtures" / "unsupported_requests.jsonl"

#: The fixture row whose abstention was measured in the E05 evaluation run.
ABSTAIN_FIXTURE_ID: Final = "unsupported-001"

#: The in-domain example from `INTERFACE_CONTRACT.md:141`.
ACCEPT_TEXT: Final = "How do I activate my new card?"

READINESS_TIMEOUT_SECONDS: Final = 180.0
READINESS_POLL_SECONDS: Final = 0.25
REQUEST_TIMEOUT_SECONDS: Final = 60.0
SHUTDOWN_TIMEOUT_SECONDS: Final = 10.0


class DemoError(RuntimeError):
    """Raised when the demonstration cannot prove what it claims to prove."""


@dataclass(frozen=True, slots=True)
class Response:
    """One HTTP response, kept as status plus decoded body."""

    status: int
    body: dict[str, Any]


def free_port() -> int:
    """Reserve and release an ephemeral port, returning its number.

    Binding port 0 asks the kernel for a free port; the socket is closed immediately so
    the child can bind it. There is a small race if something else grabs the port in
    between, which is acceptable for a local demo and much safer than assuming 8000 is
    idle — an operator running `make serve` in another terminal would otherwise see
    this fail with a confusing bind error.
    """

    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def read_fixture_text(fixture_id: str) -> str:
    """Return the text of one curated unsupported request, by ID.

    Read from the committed fixture rather than duplicated into this file, so the demo
    cannot claim an abstention for a text the evaluation never measured.
    """

    if not FIXTURE_PATH.is_file():
        raise DemoError(f"The curated unsupported-request fixture is missing: {FIXTURE_PATH}")

    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("request_id") == fixture_id:
            text = row.get("text")
            if not isinstance(text, str) or not text:
                raise DemoError(f"Fixture row {fixture_id} has no usable text")
            return text

    raise DemoError(f"Fixture row {fixture_id} is absent from {FIXTURE_PATH}")


def request(url: str, *, payload: dict[str, object] | None = None) -> Response:
    """Send one request and decode the response, treating 4xx and 5xx as data.

    An error status is part of what the demo may legitimately observe, so
    `HTTPError` is caught and unwrapped rather than raised: a 503 from `/health` is
    information, not a transport failure.
    """

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    http_request = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(http_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return Response(
                status=int(response.status),
                body=json.loads(response.read().decode("utf-8")),
            )
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return Response(status=int(error.code), body=body)


@contextmanager
def serving_process(port: int, environ: Mapping[str, str]) -> Iterator[subprocess.Popen[bytes]]:
    """Run the real service as a child process and guarantee it is stopped.

    The child is started with `-m intentguard.app`, the same entry point `make serve`
    uses, so the demo exercises the shipped path rather than a private one. Output is
    inherited so an artifact-load failure is visible in the transcript instead of being
    swallowed into a pipe nobody reads.
    """

    # Fixed argv, no shell, and no value here comes from user input.
    process = subprocess.Popen(
        [sys.executable, "-m", "intentguard.app"],
        cwd=REPOSITORY_ROOT,
        env={**environ, "INTENTGUARD_PORT": str(port), "INTENTGUARD_HOST": "127.0.0.1"},
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                # A service that ignores SIGTERM must not outlive the demo holding a
                # port; escalate rather than leaving it for the next run to trip over.
                process.kill()
                process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)


def wait_until_ready(base_url: str, process: subprocess.Popen[bytes]) -> Response:
    """Poll `/health` until it reports ready, the child dies, or the timeout expires.

    The child's liveness is checked on every iteration. Without that, a startup failure
    — a missing artifact, a checksum mismatch — would be reported as a timeout minutes
    later instead of immediately, hiding the actual cause.

    The timeout is generous because the first request loads a 265 MB bundle and
    re-hashes every file in it.
    """

    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise DemoError(
                f"The service exited with code {exit_code} before reporting ready. "
                "Its output above names the reason; a missing or invalid artifact is "
                "the usual one."
            )
        try:
            response = request(f"{base_url}/health")
        except urllib.error.URLError:
            time.sleep(READINESS_POLL_SECONDS)
            continue
        if response.status == 200:
            return response
        # A 503 means the process is listening but the artifact is not usable. That is
        # a real answer from the contract, so it is reported rather than retried away.
        raise DemoError(
            f"/health returned {response.status} rather than becoming ready: {response.body}"
        )

    raise DemoError(f"/health did not report ready within {READINESS_TIMEOUT_SECONDS:.0f}s")


def show(title: str, body: dict[str, Any]) -> None:
    """Print one labelled section of the transcript."""

    print(f"\n--- {title} ---")
    print(json.dumps(body, indent=2, sort_keys=True))


def predict(base_url: str, text: str) -> dict[str, Any]:
    """Send one prediction request and require a 200 with a decision."""

    response = request(f"{base_url}/v1/predict", payload={"text": text})
    if response.status != 200:
        raise DemoError(f"/v1/predict returned {response.status}: {response.body}")
    if "decision" not in response.body:
        raise DemoError(f"/v1/predict returned no decision: {response.body}")
    return response.body


def main() -> None:
    """Run the demonstration, or fail loudly enough to be diagnosable."""

    abstain_text = read_fixture_text(ABSTAIN_FIXTURE_ID)
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"

    print("IntentGuard strict real-artifact demonstration (AC-013)")
    print(f"Serving {sys.executable} -m intentguard.app on {base_url}")

    with serving_process(port, os.environ) as process:
        health = wait_until_ready(base_url, process)
        show("GET /health", health.body)

        accepted = predict(base_url, ACCEPT_TEXT)
        show(f"POST /v1/predict — in-domain: {ACCEPT_TEXT!r}", accepted)

        abstained = predict(base_url, abstain_text)
        show(
            f"POST /v1/predict — {ABSTAIN_FIXTURE_ID} (curated unsupported): {abstain_text!r}",
            abstained,
        )

    threshold = accepted["threshold"]
    print("\n--- Demonstration summary ---")
    print(f"model_version           {health.body['model_version']}")
    print(f"label_count             {health.body['label_count']}")
    print(f"device                  {health.body['device']}")
    print(f"threshold (persisted)   {threshold}")
    print(f"in-domain decision      {accepted['decision']} at {accepted['confidence']}")
    print(f"unsupported decision    {abstained['decision']} at {abstained['confidence']}")

    failures: list[str] = []
    if accepted["decision"] != "accept":
        failures.append(
            f"the in-domain request {ACCEPT_TEXT!r} abstained at confidence "
            f"{accepted['confidence']} against threshold {threshold}"
        )
    if accepted["intent"] is None:
        failures.append("an accepted response named no intent")
    if abstained["decision"] != "abstain":
        failures.append(
            f"the curated unsupported request {ABSTAIN_FIXTURE_ID} was accepted at "
            f"confidence {abstained['confidence']} against threshold {threshold}"
        )
    if abstained["intent"] is not None:
        failures.append(f"an abstained response named intent {abstained['intent']!r}")
    if failures:
        raise DemoError(
            "The demonstration did not show both required behaviours: "
            + "; ".join(failures)
            + ". This is a real observation about the loaded artifact, not a script "
            "defect — do not change the model or threshold to make it pass."
        )

    print(
        f"\nDemonstrated accept ({accepted['intent']}) and abstain through the real "
        f"sealed artifact {health.body['model_version']} over HTTP."
    )


if __name__ == "__main__":
    try:
        main()
    except (DemoError, OSError, ValueError) as error:
        raise SystemExit(f"Demo failed: {error}") from error
