import os
import sys
from typing import List, Optional

from upii.analysis.model_cache import model_is_cached  # noqa: F401
from upii.core.config import config


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
            # Suppress tqdm progress bars during model loading and encoding.
            from transformers.utils.logging import disable_progress_bar  # noqa: E402
            disable_progress_bar()
            import logging  # noqa: E402
            logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
            cls._instance = SentenceTransformer(model_name)
        return cls._instance

    def embed(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        model = self.get_instance()
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return embeddings.tolist()
