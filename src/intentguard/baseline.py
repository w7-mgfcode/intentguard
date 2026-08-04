"""TF-IDF plus logistic-regression baseline construction and inference.

This module is deliberately narrow: it builds a scikit-learn `Pipeline` from a
validated `BaselineConfig`, fits it, and predicts. It computes no metrics and
performs no file I/O, so the same pipeline definition is used identically by
training, evaluation, and any later comparison.

Only stock scikit-learn estimators appear here. A custom `BaseEstimator` would
be pickled by reference to this module, so any later rename or signature change
would silently break every previously saved artifact.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]

from intentguard.config import BaselineConfig
from intentguard.metrics import MetricError, label_id_array

VECTORIZER_STEP: Final = "tfidf"
CLASSIFIER_STEP: Final = "classifier"
PROBABILITY_SUM_TOLERANCE: Final = 1e-9


class BaselineError(ValueError):
    """Raised when the baseline pipeline violates its own contract."""


def build_pipeline(config: BaselineConfig, seed: int) -> Pipeline:
    """Build an unfitted TF-IDF logistic-regression pipeline from frozen configuration.

    The ten hyperparameters selected for this baseline are passed explicitly from
    `config`, so none of them can drift with a repository edit. Estimator options
    that were not selected keep their scikit-learn defaults and are therefore not
    pinned against a library upgrade; the recorded dependency versions in each
    artifact's provenance are what make a measured result reproducible.

    `multi_class` is intentionally not set: it was removed in scikit-learn 1.9,
    and `lbfgs` is multinomial by default.
    """

    return Pipeline(
        [
            (
                VECTORIZER_STEP,
                TfidfVectorizer(
                    lowercase=config.lowercase,
                    ngram_range=(config.ngram_min, config.ngram_max),
                    max_features=config.max_features,
                    min_df=config.min_df,
                    sublinear_tf=config.sublinear_tf,
                ),
            ),
            (
                CLASSIFIER_STEP,
                LogisticRegression(
                    C=config.regularization_c,
                    class_weight=config.class_weight,
                    max_iter=config.max_iter,
                    solver=config.solver,
                    random_state=seed,
                ),
            ),
        ]
    )


def fit_pipeline(
    pipeline: Pipeline,
    texts: Sequence[str],
    label_ids: Sequence[int],
    *,
    label_count: int,
) -> Pipeline:
    """Fit the pipeline on training data only and assert the learned label order.

    The fitted `classes_` order defines the column order of `predict_proba`, so it
    is asserted against the canonical label map rather than assumed. Training
    text is the only text passed here, which is what keeps the TF-IDF vocabulary
    free of validation and test tokens.
    """

    if not texts:
        raise BaselineError("Baseline training requires at least one example")
    if len(texts) != len(label_ids):
        raise BaselineError("Baseline training text and label counts differ")
    if label_count < 2:
        raise BaselineError("Baseline training requires at least two labels")

    try:
        labels = label_id_array(label_ids, "label_ids", label_count)
    except MetricError as error:
        raise BaselineError(f"Baseline training labels are invalid: {error}") from error

    observed = sorted(set(labels.tolist()))
    if observed != list(range(label_count)):
        raise BaselineError(
            f"Baseline training data must cover all {label_count} labels at least once"
        )

    pipeline.fit(list(texts), labels)

    classes = cast(NDArray[np.int64], pipeline.named_steps[CLASSIFIER_STEP].classes_)
    if classes.tolist() != list(range(label_count)):
        raise BaselineError(
            "Fitted classifier class order does not match the canonical label map"
        )
    return pipeline


def vocabulary(pipeline: Pipeline) -> frozenset[str]:
    """Return the fitted TF-IDF vocabulary, used to assert train-only fitting."""

    return frozenset(pipeline.named_steps[VECTORIZER_STEP].vocabulary_)


def analyzer(pipeline: Pipeline) -> Callable[[str], list[str]]:
    """Return the vectorizer's own analyzer, so callers tokenise as it does.

    Any diagnostic that compares text against `vocabulary()` must use this rather
    than an ad-hoc split. The vectorizer applies its own preprocessing, token
    pattern, and n-gram range, so a naive `str.split()` reports terms the model
    never had the chance to learn.
    """

    return cast(
        Callable[[str], list[str]], pipeline.named_steps[VECTORIZER_STEP].build_analyzer()
    )


def predict_probabilities(
    pipeline: Pipeline, texts: Sequence[str], *, label_count: int
) -> NDArray[np.float64]:
    """Predict a validated probability matrix with one column per canonical label."""

    if not texts:
        raise BaselineError("Baseline prediction requires at least one example")

    probabilities = np.asarray(pipeline.predict_proba(list(texts)), dtype=np.float64)
    if probabilities.shape != (len(texts), label_count):
        raise BaselineError(
            f"Probability matrix shape {probabilities.shape} is not "
            f"{(len(texts), label_count)}"
        )
    row_sums = probabilities.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=PROBABILITY_SUM_TOLERANCE, rtol=0.0):
        raise BaselineError("Probability rows do not sum to one within tolerance")
    return probabilities


def labels_from_probabilities(probabilities: NDArray[np.float64]) -> list[int]:
    """Take the argmax label per row, so labels and probabilities can never disagree."""

    return [int(index) for index in probabilities.argmax(axis=1)]
