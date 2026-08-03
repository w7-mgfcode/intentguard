"""Prepare the pinned BANKING77 data contract and emit deterministic provenance."""

from __future__ import annotations

import json
from pathlib import Path

from intentguard.config import load_foundation_config
from intentguard.data import (
    DataContractError,
    load_pinned_dataset,
    prepare_dataset,
    provenance_directory,
    write_provenance,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Load, validate, split, and record the approved BANKING77 revision."""

    try:
        config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
        prepared = prepare_dataset(load_pinned_dataset(config), config)
        output_path = write_provenance(prepared, provenance_directory(config))
    except DataContractError as error:
        raise SystemExit(f"BANKING77 data preparation failed: {error}") from error

    summary = {
        "dataset_id": config.dataset_id,
        "dataset_revision": config.dataset_revision,
        "derived_split_counts": prepared.provenance["derived_split_counts"],
        "label_map_sha256": prepared.provenance["label_map_sha256"],
        "provenance_path": str(output_path),
        "split_fingerprints": prepared.provenance["split_fingerprints"],
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
