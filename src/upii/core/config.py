import os
from pathlib import Path
from dataclasses import dataclass, fields
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
    # Relational defaults to 0.0: ingestion now populates the knowledge graph, so the
    # signal is LIVE and available (raise it via `upii ask --w-relational`), but on the
    # retrieval eval it is not yet net-positive — boosting on a non-discriminating query
    # entity (e.g. the product's own name) can displace a better semantic hit, dipping
    # Recall@1 while Recall@10 holds. Kept at 0 until it is tuned to help; see
    # eval/results/REPORT.md and docs/evidence.md (Phase 4).
    fusion_weight_relational: float = 0.0
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
                data = yaml.safe_load(f) or {}
            # Tolerate keys this dataclass doesn't know about (e.g. an `mcp:` block
            # a user adds per docs/mcp_setup.md) rather than crashing startup with a
            # TypeError. MCP settings have their own loader (upii.mcp.config).
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})
        return cls()

config = Config.load()
