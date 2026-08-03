from pathlib import Path

from intentguard.config import (
    BANKING77_DATASET_ID,
    BANKING77_DATASET_REVISION,
    STATUS_VOCABULARY,
    UNRESOLVED_REVISION,
    load_foundation_config,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_default_configuration_loads_foundation_contract() -> None:
    config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")

    assert config.seed == 42
    assert config.dataset_id == BANKING77_DATASET_ID
    assert config.dataset_revision == BANKING77_DATASET_REVISION
    assert config.validation_fraction == 0.15
    assert config.data_root == Path("data")
    assert config.base_model_id == "distilbert/distilbert-base-uncased"
    assert config.base_model_revision == UNRESOLVED_REVISION
    assert config.status_vocabulary == STATUS_VOCABULARY
