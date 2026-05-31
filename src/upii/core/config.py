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
    # LLM & RAG
    llm_model: str = "llama3.2" # Default to fast model
    embedding_model: str = "all-MiniLM-L6-v2"
    rag_min_similarity: float = 0.5
    rag_min_similarity: float = 0.5
    rag_max_chunks: int = 5
    
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
