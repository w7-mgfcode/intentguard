"""Contract tests for the TF-IDF logistic-regression baseline pipeline.

These use a small synthetic corpus so the suite stays fast. The properties under
test — determinism, class ordering, probability shape, train-only vocabulary, and
convergence — are structural and do not depend on BANKING77 itself.
"""

from __future__ import annotations

import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]

from intentguard.baseline import (
    CLASSIFIER_STEP,
    VECTORIZER_STEP,
    BaselineError,
    build_pipeline,
    fit_pipeline,
    labels_from_probabilities,
    predict_probabilities,
    vocabulary,
)
from intentguard.config import BaselineConfig, load_foundation_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SEED = 42
LABEL_COUNT = 3

TRAIN_TEXTS = (
    "card payment declined at the shop",
    "my card payment was declined again",
    "declined card payment yesterday",
    "transfer money to another account",
    "how do i transfer funds abroad",
    "money transfer is still pending",
    "verify my identity documents",
    "identity verification documents needed",
    "please verify identity now",
)
TRAIN_LABELS = (0, 0, 0, 1, 1, 1, 2, 2, 2)
HELD_OUT_TEXTS = (
    "card payment declined unexpectedly",
    "transfer funds to a friend",
    "verify identity please",
)


def _config() -> BaselineConfig:
    return load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml").baseline


def _fitted(config: BaselineConfig | None = None) -> Pipeline:
    resolved = config or _config()
    return fit_pipeline(
        build_pipeline(resolved, SEED), TRAIN_TEXTS, TRAIN_LABELS, label_count=LABEL_COUNT
    )


def test_pipeline_uses_only_stock_scikit_learn_estimators() -> None:
    pipeline = build_pipeline(_config(), SEED)
    for step in (VECTORIZER_STEP, CLASSIFIER_STEP):
        module = type(pipeline.named_steps[step]).__module__
        assert module.startswith("sklearn."), f"{step} must be a stock scikit-learn estimator"


def test_pipeline_passes_every_configured_hyperparameter() -> None:
    config = _config()
    pipeline = build_pipeline(config, SEED)
    vectorizer = pipeline.named_steps[VECTORIZER_STEP]
    classifier = pipeline.named_steps[CLASSIFIER_STEP]

    assert vectorizer.lowercase == config.lowercase
    assert vectorizer.ngram_range == (config.ngram_min, config.ngram_max)
    assert vectorizer.max_features == config.max_features
    assert vectorizer.min_df == config.min_df
    assert vectorizer.sublinear_tf == config.sublinear_tf
    assert config.regularization_c == classifier.C
    assert classifier.class_weight == config.class_weight
    assert classifier.max_iter == config.max_iter
    assert classifier.solver == config.solver
    assert classifier.random_state == SEED


def test_multi_class_is_not_set() -> None:
    classifier = build_pipeline(_config(), SEED).named_steps[CLASSIFIER_STEP]
    assert "multi_class" not in classifier.get_params()


def test_two_fits_produce_identical_labels_and_probabilities() -> None:
    first = predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT)
    second = predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT)

    assert labels_from_probabilities(first) == labels_from_probabilities(second)
    assert np.array_equal(first, second)


def test_class_order_equals_the_canonical_label_map() -> None:
    classifier = _fitted().named_steps[CLASSIFIER_STEP]
    assert classifier.classes_.tolist() == list(range(LABEL_COUNT))


def test_probability_matrix_has_one_column_per_label() -> None:
    probabilities = predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT)
    assert probabilities.shape == (len(HELD_OUT_TEXTS), LABEL_COUNT)


def test_probability_rows_sum_to_one() -> None:
    probabilities = predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT)
    assert np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-9, rtol=0.0)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)


def test_vocabulary_is_fitted_on_training_text_only() -> None:
    pipeline = _fitted()
    learned = vocabulary(pipeline)

    assert learned, "The fitted vocabulary must not be empty"
    held_out_only_tokens = {"unexpectedly", "friend"}
    assert held_out_only_tokens.isdisjoint(learned)
    assert "declined" in learned


def test_fitting_does_not_emit_a_convergence_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        _fitted()


def test_labels_are_the_argmax_of_the_probability_matrix() -> None:
    probabilities = predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT)
    assert labels_from_probabilities(probabilities) == [
        int(row.argmax()) for row in probabilities
    ]


def test_the_baseline_learns_the_synthetic_corpus() -> None:
    probabilities = predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT)
    assert labels_from_probabilities(probabilities) == [0, 1, 2]


def test_fit_rejects_empty_training_data() -> None:
    with pytest.raises(BaselineError, match="at least one example"):
        fit_pipeline(build_pipeline(_config(), SEED), (), (), label_count=LABEL_COUNT)


def test_fit_rejects_mismatched_text_and_label_counts() -> None:
    with pytest.raises(BaselineError, match="counts differ"):
        fit_pipeline(
            build_pipeline(_config(), SEED), TRAIN_TEXTS, TRAIN_LABELS[:-1], label_count=LABEL_COUNT
        )


def test_fit_rejects_a_degenerate_label_map() -> None:
    with pytest.raises(BaselineError, match="at least two labels"):
        fit_pipeline(build_pipeline(_config(), SEED), TRAIN_TEXTS, TRAIN_LABELS, label_count=1)


def test_fit_rejects_training_data_missing_a_label() -> None:
    with pytest.raises(BaselineError, match="must cover all 4 labels"):
        fit_pipeline(build_pipeline(_config(), SEED), TRAIN_TEXTS, TRAIN_LABELS, label_count=4)


def test_predict_rejects_empty_input() -> None:
    with pytest.raises(BaselineError, match="at least one example"):
        predict_probabilities(_fitted(), (), label_count=LABEL_COUNT)


def test_predict_rejects_an_unexpected_column_count() -> None:
    with pytest.raises(BaselineError, match="is not"):
        predict_probabilities(_fitted(), HELD_OUT_TEXTS, label_count=LABEL_COUNT + 1)


def test_class_weight_none_is_accepted() -> None:
    unweighted = replace(_config(), class_weight=None)
    assert build_pipeline(unweighted, SEED).named_steps[CLASSIFIER_STEP].class_weight is None
    predict_probabilities(_fitted(unweighted), HELD_OUT_TEXTS, label_count=LABEL_COUNT)
