# Data directory

`make data` populates this directory with locally generated BANKING77 cache and provenance outputs under U02. Generated contents are ignored by Git; this README is the tracked contract.

The approved source is `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`.
The command writes deterministic provenance to
`data/banking77-1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8/provenance.json` and
stores its reusable Hugging Face cache under `data/cache/`.
