# ADR-0001: DistilBERT with Hugging Face Transformers and PyTorch

- **Status:** Accepted
- **Date:** 2026-07-31

## Context

The portfolio project must demonstrate modern NLP model work, PyTorch or
TensorFlow, Hugging Face, reproducible evaluation, and local execution on an RTX
5060 Mobile with 24 GB RAM. It must also finish in one weekend.

The improved method needs to be substantial enough to compare against a lexical
baseline but small enough to fine-tune and serve locally.

## Decision

Use `distilbert-base-uncased` through Hugging Face Transformers with PyTorch and
a 77-class sequence-classification head.

Use two epochs initially, sequence length 96, train batch size 16, validation
macro-F1 for epoch selection, and one documented OOM fallback to batch size 8.

## Alternatives considered

### TF-IDF only

Fast and credible as a baseline, but insufficient to demonstrate Hugging
Face/PyTorch fine-tuning.

### Frozen sentence embeddings plus logistic regression

Lower implementation risk and valid as a fallback, but demonstrates less
end-to-end transformer training.

### BERT-base, RoBERTa or DeBERTa

Potentially stronger but larger/slower. Additional performance is not required
to prove the engineering point.

### Small generative LLM

Would make classification slower, harder to calibrate, and harder to evaluate
without adding business value.

### TensorFlow

Technically valid, but the user’s local workflow and target portfolio benefit
more from a straightforward PyTorch/Hugging Face path. Supporting both
frameworks would be decorative.

## Consequences

### Positive

- Real transformer fine-tuning and inference.
- Comfortable local footprint.
- Mature training and artifact APIs.
- Clear comparison with the lexical baseline.
- CPU inference remains feasible.

### Negative

- Fine-tuning environment and CUDA compatibility are the largest weekend risks.
- Maximum softmax probabilities may be poorly calibrated.
- DistilBERT is English-specific and not the newest architecture.
- Results may vary slightly across hardware and library releases.

## Reconsideration trigger

Reconsider only if:

- the checkpoint cannot load or make a forward pass on the target environment;
- fine-tuning cannot produce a valid artifact by Hour 9 after the documented
  fallback;
- measured latency or memory exceeds the hardware budget;
- the target role explicitly requires TensorFlow or multilingual modeling.

The weekend fallback is frozen DistilBERT embeddings plus logistic regression,
reported as a partial deviation—not an unannounced architecture change.

