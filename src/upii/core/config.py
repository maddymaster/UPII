import os
from pathlib import Path
from dataclasses import dataclass
import yaml

@dataclass
class Config:
    db_path: str = "upii.db"
    vector_store_path: str = "upii_vectors"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    # Identity (used for self-authored style filtering & signatures)
    user_name: str = "Maddy"
    # LLM & RAG
    llm_model: str = "llama3.2" # Default to fast model
    embedding_model: str = "all-MiniLM-L6-v2"
    rag_min_similarity: float = 0.5
    rag_max_chunks: int = 5

    # --- v2 fusion ranking -------------------------------------------------
    # The rehydrator scores every candidate chunk on three signals, each
    # normalised to [0,1], then combines them as a weighted sum:
    #   fused = w_semantic*semantic + w_temporal*temporal + w_relational*relational
    # Semantic dominates; temporal/relational are re-ranking boosts. Tuned on the
    # eval set in eval/ (Recall@10 >= 0.85). Override per-call via `upii ask` flags.
    fusion_weight_semantic: float = 1.0
    fusion_weight_temporal: float = 0.25
    fusion_weight_relational: float = 0.5
    # Recency / calendar-proximity half-life in days: a chunk/event this old
    # contributes half of a fresh one to the temporal signal.
    temporal_halflife_days: float = 30.0

    def fusion_weights(self) -> dict:
        """Current fusion weights as a ``{signal: weight}`` dict."""
        return {
            "semantic": self.fusion_weight_semantic,
            "temporal": self.fusion_weight_temporal,
            "relational": self.fusion_weight_relational,
        }

    # Gemini Settings
    # Prefer the GEMINI_API_KEY env var; fall back to the hardcoded demo key.
    # Renew an expired key at https://aistudio.google.com/apikey
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.5-flash"

    
    # v1.0 Ambient Settings
    staging_db_path: str = "staging.db"

    @classmethod
    def load(cls, config_path: str = ".upii_config.yaml") -> "Config":
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                return cls(**data)
        return cls()

config = Config.load()
