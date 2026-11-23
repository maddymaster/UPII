"""Pure-fs model-cache checks used by both doctor and embeddings.

No ML libraries are imported so that ``upii doctor`` can run without pulling in
sentence-transformers / huggingface_hub / torch.
"""

import glob
import os
from typing import List

_WEIGHTS = ("model.safetensors", "pytorch_model.bin")


def _hub_cache_dirs() -> List[str]:
    """Where a SentenceTransformer model may already be cached, in lookup order."""
    dirs: list[str] = []
    if os.environ.get("SENTENCE_TRANSFORMERS_HOME"):
        dirs.append(os.environ["SENTENCE_TRANSFORMERS_HOME"])
    if os.environ.get("HF_HUB_CACHE"):
        dirs.append(os.environ["HF_HUB_CACHE"])
    elif os.environ.get("HF_HOME"):
        dirs.append(os.path.join(os.environ["HF_HOME"], "hub"))
    else:
        xdg = os.environ.get("XDG_CACHE_HOME") or os.path.join(
            os.path.expanduser("~"), ".cache"
        )
        dirs.append(os.path.join(xdg, "huggingface", "hub"))
    return dirs


def model_is_cached(model_name: str) -> bool:
    """True if *model_name* loads without the network.

    Pure filesystem check: importing huggingface_hub to ask would freeze its
    ``HF_HUB_OFFLINE`` setting before we choose it.
    """
    if os.path.isdir(model_name):
        return True
    repo = model_name if "/" in model_name else f"sentence-transformers/{model_name}"
    folder = "models--" + repo.replace("/", "--")
    for cache in _hub_cache_dirs():
        for snap in glob.glob(os.path.join(cache, folder, "snapshots", "*")):
            if os.path.isfile(os.path.join(snap, "modules.json")) and any(
                os.path.isfile(os.path.join(snap, w)) for w in _WEIGHTS
            ):
                return True
    return False
