from pathlib import Path

from intentguard.config import STATUS_VOCABULARY, UNRESOLVED_REVISION, load_foundation_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_default_configuration_loads_foundation_contract() -> None:
    config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")

    assert config.seed == 42
    assert config.dataset_id == "PolyAI/banking77"
    assert config.base_model_id == "distilbert/distilbert-base-uncased"
    assert config.dataset_revision == UNRESOLVED_REVISION
    assert config.base_model_revision == UNRESOLVED_REVISION
    assert config.status_vocabulary == STATUS_VOCABULARY
