"""Pinned BANKING77 loading, split validation, and provenance generation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final, cast

import datasets  # type: ignore[import-untyped]
from datasets import ClassLabel, Dataset, DatasetDict, load_dataset
from sklearn.model_selection import StratifiedShuffleSplit  # type: ignore[import-untyped]

from intentguard.config import FoundationConfig
from intentguard.schemas import CanonicalExample, PreparedDataset, SplitName

UPSTREAM_TRAIN_COUNT: Final = 10_003
UPSTREAM_TEST_COUNT: Final = 3_080
LABEL_COUNT: Final = 77
DATASET_LICENSE: Final = "CC-BY-4.0"
DATASET_LICENSE_REFERENCE: Final = "https://creativecommons.org/licenses/by/4.0/"
CANONICAL_LABEL_NAMES: Final = (
    "activate_my_card",
    "age_limit",
    "apple_pay_or_google_pay",
    "atm_support",
    "automatic_top_up",
    "balance_not_updated_after_bank_transfer",
    "balance_not_updated_after_cheque_or_cash_deposit",
    "beneficiary_not_allowed",
    "cancel_transfer",
    "card_about_to_expire",
    "card_acceptance",
    "card_arrival",
    "card_delivery_estimate",
    "card_linking",
    "card_not_working",
    "card_payment_fee_charged",
    "card_payment_not_recognised",
    "card_payment_wrong_exchange_rate",
    "card_swallowed",
    "cash_withdrawal_charge",
    "cash_withdrawal_not_recognised",
    "change_pin",
    "compromised_card",
    "contactless_not_working",
    "country_support",
    "declined_card_payment",
    "declined_cash_withdrawal",
    "declined_transfer",
    "direct_debit_payment_not_recognised",
    "disposable_card_limits",
    "edit_personal_details",
    "exchange_charge",
    "exchange_rate",
    "exchange_via_app",
    "extra_charge_on_statement",
    "failed_transfer",
    "fiat_currency_support",
    "get_disposable_virtual_card",
    "get_physical_card",
    "getting_spare_card",
    "getting_virtual_card",
    "lost_or_stolen_card",
    "lost_or_stolen_phone",
    "order_physical_card",
    "passcode_forgotten",
    "pending_card_payment",
    "pending_cash_withdrawal",
    "pending_top_up",
    "pending_transfer",
    "pin_blocked",
    "receiving_money",
    "Refund_not_showing_up",
    "request_refund",
    "reverted_card_payment?",
    "supported_cards_and_currencies",
    "terminate_account",
    "top_up_by_bank_transfer_charge",
    "top_up_by_card_charge",
    "top_up_by_cash_or_cheque",
    "top_up_failed",
    "top_up_limits",
    "top_up_reverted",
    "topping_up_by_card",
    "transaction_charged_twice",
    "transfer_fee_charged",
    "transfer_into_account",
    "transfer_not_received_by_recipient",
    "transfer_timing",
    "unable_to_verify_identity",
    "verify_my_identity",
    "verify_source_of_funds",
    "verify_top_up",
    "virtual_card_not_working",
    "visa_or_mastercard",
    "why_verify_identity",
    "wrong_amount_of_cash_received",
    "wrong_exchange_rate_for_cash_withdrawal",
)
CANONICAL_LABEL_MAP_SHA256: Final = (
    "0a3f622029033ef1cfe378833a431fc243d7c9d856b50717c479f95c0b8ca5d2"
)


class DataContractError(ValueError):
    """Raised when pinned data cannot satisfy the IntentGuard contract."""


def load_pinned_dataset(config: FoundationConfig) -> DatasetDict:
    """Load the approved revision through one cache-aware data boundary."""

    cache_dir = config.data_root / "cache"
    try:
        loaded = load_dataset(
            config.dataset_id,
            revision=config.dataset_revision,
            cache_dir=str(cache_dir),
        )
    except Exception as error:
        raise DataContractError(
            f"Unable to load {config.dataset_id}@{config.dataset_revision}; "
            "connect once to populate "
            f"the verified cache at {cache_dir} or restore a cache with matching provenance."
        ) from error
    if not isinstance(loaded, DatasetDict):
        raise DataContractError(
            f"Pinned dataset {config.dataset_id}@{config.dataset_revision} loader "
            "must return a DatasetDict"
        )
    return loaded


def _label_names(dataset: Dataset) -> tuple[str, ...]:
    label_feature = dataset.features.get("label")
    if not isinstance(label_feature, ClassLabel):
        raise DataContractError("The pinned dataset label field must be a ClassLabel")
    names = tuple(label_feature.names)
    if len(names) != LABEL_COUNT or len(set(names)) != LABEL_COUNT:
        raise DataContractError("The pinned dataset must expose exactly 77 unique label names")
    if any(not name for name in names):
        raise DataContractError("The pinned dataset label mapping contains an empty name")
    if names != CANONICAL_LABEL_NAMES:
        raise DataContractError(
            "The pinned dataset label mapping does not match the approved canonical order"
        )
    return names


def _canonical_examples(
    dataset: Dataset,
    source_split: str,
    output_split: SplitName,
    label_names: tuple[str, ...],
) -> tuple[CanonicalExample, ...]:
    required_columns = {"text", "label"}
    if not required_columns <= set(dataset.column_names):
        raise DataContractError("The pinned dataset must contain text and label fields")

    examples: list[CanonicalExample] = []
    for index, row in enumerate(dataset, start=1):
        text = row.get("text")
        label_id = row.get("label")
        if not isinstance(text, str) or not text.strip():
            raise DataContractError(f"{source_split}:{index:06d} has empty or invalid text")
        if not isinstance(label_id, int) or isinstance(label_id, bool):
            raise DataContractError(f"{source_split}:{index:06d} has invalid label")
        if not 0 <= label_id < len(label_names):
            raise DataContractError(f"{source_split}:{index:06d} has an out-of-range label")
        examples.append(
            CanonicalExample(
                example_id=f"{source_split}:{index:06d}",
                text=text,
                label_id=label_id,
                label_name=label_names[label_id],
                split=output_split,
            )
        )
    return tuple(examples)


def _split_train_validation(
    source_train: tuple[CanonicalExample, ...],
    seed: int,
    validation_fraction: float,
) -> tuple[tuple[CanonicalExample, ...], tuple[CanonicalExample, ...]]:
    labels = [example.label_id for example in source_train]
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=validation_fraction, random_state=seed)
    try:
        train_indices, validation_indices = next(splitter.split(source_train, labels))
    except ValueError as error:
        raise DataContractError(
            "Unable to derive the configured stratified validation split"
        ) from error

    train_index_set = set(cast(list[int], train_indices.tolist()))
    validation_index_set = set(cast(list[int], validation_indices.tolist()))
    if train_index_set & validation_index_set:
        raise DataContractError("Derived train and validation memberships overlap")
    train = tuple(
        replace(example, split="train")
        for index, example in enumerate(source_train)
        if index in train_index_set
    )
    validation = tuple(
        replace(example, split="validation")
        for index, example in enumerate(source_train)
        if index in validation_index_set
    )
    return train, validation


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _split_fingerprint(examples: tuple[CanonicalExample, ...]) -> str:
    payload = [
        {
            "example_id": example.example_id,
            "label_id": example.label_id,
            "label_name": example.label_name,
            "split": example.split,
            "text": example.text,
        }
        for example in examples
    ]
    return _hash_payload(payload)


def _duplicate_text_statistics(
    splits: dict[SplitName, tuple[CanonicalExample, ...]],
) -> dict[str, object]:
    counters = {
        name: Counter(example.text for example in examples) for name, examples in splits.items()
    }
    per_split = {
        name: {
            "duplicate_examples": sum(count - 1 for count in counter.values() if count > 1),
            "unique_texts": len(counter),
        }
        for name, counter in counters.items()
    }
    pairs: dict[str, dict[str, int]] = {}
    ordered_names: tuple[SplitName, ...] = ("train", "validation", "test")
    for position, first_name in enumerate(ordered_names):
        for second_name in ordered_names[position + 1 :]:
            shared_texts = set(counters[first_name]) & set(counters[second_name])
            pairs[f"{first_name}:{second_name}"] = {
                "shared_example_pairs": sum(
                    counters[first_name][text] * counters[second_name][text]
                    for text in shared_texts
                ),
                "shared_texts": len(shared_texts),
            }
    return {"per_split": per_split, "split_pairs": pairs}


def validate_prepared_dataset(prepared: PreparedDataset) -> None:
    """Reject overlap, schema drift, and label-map inconsistency before output."""

    splits: dict[SplitName, tuple[CanonicalExample, ...]] = {
        "train": prepared.train,
        "validation": prepared.validation,
        "test": prepared.test,
    }
    identifiers: dict[str, SplitName] = {}
    for split_name, examples in splits.items():
        for example in examples:
            if example.split != split_name:
                raise DataContractError(
                    f"Example {example.example_id} has inconsistent split membership"
                )
            if example.example_id in identifiers:
                raise DataContractError(
                    f"Example ID overlaps {identifiers[example.example_id]} and {split_name}"
                )
            identifiers[example.example_id] = split_name
            if not example.text.strip():
                raise DataContractError(f"Example {example.example_id} has empty text")
            if not 0 <= example.label_id < len(prepared.label_names):
                raise DataContractError(f"Example {example.example_id} has invalid label ID")
            if example.label_name != prepared.label_names[example.label_id]:
                raise DataContractError(f"Example {example.example_id} has inconsistent label name")
    if len(prepared.label_names) != LABEL_COUNT or len(set(prepared.label_names)) != LABEL_COUNT:
        raise DataContractError("Prepared dataset must retain exactly 77 unique label names")


def prepare_dataset(source: DatasetDict, config: FoundationConfig) -> PreparedDataset:
    """Validate source splits, derive validation only from source train, and fingerprint outputs."""

    if set(source.keys()) != {"train", "test"}:
        raise DataContractError(
            "Pinned BANKING77 source must contain exactly train and test splits"
        )
    if len(source["train"]) != UPSTREAM_TRAIN_COUNT or len(source["test"]) != UPSTREAM_TEST_COUNT:
        raise DataContractError(
            "Pinned BANKING77 source split counts must be exactly 10003 train and 3080 test"
        )
    label_names = _label_names(source["train"])
    if _label_names(source["test"]) != label_names:
        raise DataContractError("Pinned BANKING77 train and test label mappings differ")
    source_train = _canonical_examples(source["train"], "train", "train", label_names)
    test = _canonical_examples(source["test"], "test", "test", label_names)
    train, validation = _split_train_validation(
        source_train, config.seed, config.validation_fraction
    )
    if len(train) != 8_502 or len(validation) != 1_501:
        raise DataContractError(
            "Derived BANKING77 train and validation counts do not match the approved split"
        )

    splits: dict[SplitName, tuple[CanonicalExample, ...]] = {
        "train": train,
        "validation": validation,
        "test": test,
    }
    fingerprints = {name: _split_fingerprint(examples) for name, examples in splits.items()}
    provenance: dict[str, object] = {
        "schema_version": 1,
        "source": {
            "dataset_id": config.dataset_id,
            "dataset_revision": config.dataset_revision,
            "license": DATASET_LICENSE,
            "license_reference": DATASET_LICENSE_REFERENCE,
        },
        "datasets_version": datasets.__version__,
        "source_split_counts": {"train": len(source_train), "test": len(test)},
        "derived_split_counts": {name: len(examples) for name, examples in splits.items()},
        "validation": {
            "fraction": config.validation_fraction,
            "seed": config.seed,
            "strategy": "StratifiedShuffleSplit",
            "source_split": "train",
        },
        "label_names": list(label_names),
        "label_map_sha256": _hash_payload(list(label_names)),
        "split_fingerprints": fingerprints,
        "duplicate_text_statistics": _duplicate_text_statistics(splits),
    }
    prepared = PreparedDataset(
        train=train,
        validation=validation,
        test=test,
        label_names=label_names,
        provenance=provenance,
    )
    validate_prepared_dataset(prepared)
    return prepared


def write_provenance(prepared: PreparedDataset, output_directory: Path) -> Path:
    """Write the deterministic provenance document atomically under the generated data root."""

    output_directory.mkdir(parents=True, exist_ok=True)
    destination = output_directory / "provenance.json"
    payload = json.dumps(prepared.provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_directory,
            prefix="provenance.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        temporary.replace(destination)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return destination


def provenance_directory(config: FoundationConfig) -> Path:
    """Return the revision-scoped generated-output directory."""

    return config.data_root / f"banking77-{config.dataset_revision}"
