import os
import shutil
import logging
from typing import Dict, Any, List
import ollama
from upii.core.config import config
from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore

logger = logging.getLogger(__name__)

class Doctor:
    """System health checks."""

    def check_all(self) -> Dict[str, Any]:
        return {
            "sqlite": self.check_sqlite(),
            "vector_db": self.check_vector_db(),
            "disk": self.check_disk(),
            "model": self.check_model(),
            "ingestion": self.check_last_ingestion()
        }

    def check_sqlite(self) -> str:
        try:
            if not os.path.exists(config.db_path):
                return "FAIL: DB file missing"
            db = DB()
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.close()
            return "OK"
        except Exception as e:
            return f"FAIL: {e}"

    def check_vector_db(self) -> str:
        try:
            if not os.path.exists(config.vector_store_path):
                return "FAIL: Vector path missing"
            vs = LocalVectorStore()
            count = vs.count()
            return f"OK ({count} vectors)"
        except Exception as e:
            return f"FAIL: {e}"

    def check_disk(self) -> str:
        try:
            # Check current directory partition
            total, used, free = shutil.disk_usage(".")
            free_gb = free // (2**30)
            if free_gb < 1:
                return f"WARN: Low disk space ({free_gb} GB free)"
            return f"OK ({free_gb} GB free)"
        except Exception as e:
            return f"FAIL: {e}"

    def check_model(self) -> str:
        try:
            # Check for mock fallback in LocalLLM
            from upii.analysis.llm import LocalLLM
            llm = LocalLLM()
            if llm.is_mock:
                 return "WARN: Ollama offline (Using Mock LLM)"
            
            # Verify we can talk to Ollama.
            # Older ollama clients return a plain dict with 'models' -> [{'name': ...}].
            # Newer clients (>=0.4) return a Pydantic ListResponse with .models -> [Model(model='...')].
            resp = ollama.list()
            raw_models = getattr(resp, "models", None)
            if raw_models is None and isinstance(resp, dict):
                raw_models = resp.get("models", [])
            raw_models = raw_models or []

            model_names = []
            for m in raw_models:
                name = getattr(m, "model", None) or getattr(m, "name", None)
                if name is None and isinstance(m, dict):
                    name = m.get("model") or m.get("name")
                if name:
                    model_names.append(name)
            
            # config.llm_model might be "llama3.2" or "llama3.2:latest"
            # We do a loose check
            if any(config.llm_model in m for m in model_names):
                 return f"OK (Found {config.llm_model})"
            
            return f"WARN: Model {config.llm_model} not found in Ollama list: {model_names}"
        except Exception as e:
            return f"FAIL: Ollama connection error: {e}"

    def check_last_ingestion(self) -> str:
        try:
            db = DB()
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT MAX(ingestion_time) FROM documents")
            last = cur.fetchone()[0]
            conn.close()
            if not last:
                return "WARN: No documents ingested yet"
            return f"OK (Last: {last})"
        except Exception as e:
            return f"FAIL: {e}"
