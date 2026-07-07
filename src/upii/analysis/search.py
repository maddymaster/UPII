from typing import List, Optional, Dict
from datetime import datetime, timedelta
import json
from upii.core.types import Chunk
from upii.storage.vector import LocalVectorStore
from upii.analysis.embeddings import Embedder
from upii.storage.db import DB

class SearchEngine:
    def __init__(self):
        self.vector_store = LocalVectorStore()
        self.embedder = Embedder.get_instance()
        self.db = DB()
        self.db.init_db()


    def search(
        self,
        query: str,
        time_filter: Optional[str] = None,
        limit: int = 5,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[Chunk]:
        """
        Unified search via the v2 fusion ContextRehydrator.

        Returns RankedChunks (compatible with Chunk). ``weights`` optionally
        overrides the configured fusion weights for this call.
        """
        # Metric Tracking
        try:
            from upii.analysis.metrics import MetricsCollector
            MetricsCollector().track_query()
        except Exception:
            pass # Fail safe

        from upii.analysis.rehydration import ContextRehydrator
        rehydrator = ContextRehydrator()
        return rehydrator.rehydrate(query, time_filter, limit, weights=weights)
