# Sources

Accessed 2026-07-31.

## Dataset

- [BANKING77 Hugging Face dataset card](https://huggingface.co/datasets/PolyAI/banking77)
  — dataset description, 13,083 examples, 77 intents, English task and CC BY
  4.0 licence metadata.
- [BANKING77 upstream repository](https://github.com/PolyAI-LDN/task-specific-datasets)
  — original task-specific dataset collection and train/test statistics.
- [BANKING77 paper](https://arxiv.org/abs/2003.04807)
  — task motivation and dataset design.

## Model and framework

- [DistilBERT base uncased model card](https://huggingface.co/distilbert/distilbert-base-uncased)
  — base checkpoint information and intended downstream fine-tuning use.
- [Hugging Face Transformers documentation](https://huggingface.co/docs/transformers/index)
  — model loading, tokenization, training and inference APIs.
- [PyTorch reproducibility notes](https://docs.pytorch.org/docs/stable/notes/randomness.html)
  — seeds, deterministic-algorithm controls and cross-platform limitations.

## Implementation note

The implementation must pin concrete dataset and model revisions after verifying
them in the development environment. This specification deliberately avoids
inventing revision hashes or package versions before that verification.

