import glob
import os
import sys
from typing import List, Optional

from upii.core.config import config

_WEIGHTS = ("model.safetensors", "pytorch_model.bin")


def _hub_cache_dirs() -> List[str]:
    """Where a SentenceTransformer model may already be cached, in lookup order."""
    dirs = []
    if os.environ.get("SENTENCE_TRANSFORMERS_HOME"):
        dirs.append(os.environ["SENTENCE_TRANSFORMERS_HOME"])
    if os.environ.get("HF_HUB_CACHE"):
        dirs.append(os.environ["HF_HUB_CACHE"])
    elif os.environ.get("HF_HOME"):
        dirs.append(os.path.join(os.environ["HF_HOME"], "hub"))
    else:
        xdg = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        dirs.append(os.path.join(xdg, "huggingface", "hub"))
    return dirs


def model_is_cached(model_name: str) -> bool:
    """True if ``model_name`` loads without the network: a local folder, or a hub
    snapshot holding ``modules.json`` and weights. Pure filesystem: importing
    huggingface_hub to ask would freeze its offline setting before we choose it."""
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


def prefer_offline_if_cached(model_name: Optional[str] = None) -> bool:
    """Set HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE when the embedding model is cached,
    so loading it never waits on a Hugging Face metadata check (demos, no Wi-Fi).

    An explicit value of either variable always wins (``HF_HUB_OFFLINE=0`` turns the
    check back on, e.g. to pull a model update). Returns True if offline was set.
    """
    if "HF_HUB_OFFLINE" in os.environ or "TRANSFORMERS_OFFLINE" in os.environ:
        return False
    if not model_is_cached(model_name or getattr(config, "embedding_model", "all-MiniLM-L6-v2")):
        return False
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    # huggingface_hub reads the variable once, at import; if something imported it
    # first, update the constant it already computed.
    constants = sys.modules.get("huggingface_hub.constants")
    if constants is not None:
        constants.HF_HUB_OFFLINE = True
    return True


# Must run before sentence_transformers (and with it huggingface_hub) is imported.
prefer_offline_if_cached()

from sentence_transformers import SentenceTransformer  # noqa: E402


class Embedder:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            model_name = getattr(config, 'embedding_model', 'all-MiniLM-L6-v2')
            cls._instance = SentenceTransformer(model_name)
        return cls._instance

    def embed(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        model = self.get_instance()
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return embeddings.tolist()
