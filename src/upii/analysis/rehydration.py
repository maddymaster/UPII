
from typing import List, Dict, Optional, Set
from dataclasses import asdict
from datetime import datetime, timedelta
import json

from upii.core.types import Chunk, RankedChunk
from upii.analysis.entity_extractor import EntityExtractor
from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore
from upii.analysis.embeddings import Embedder

class ContextRehydrator:
    """
    Unified pipeline for assembling and ranking context from:
    - Vector Search (Semantic)
    - Calendar (Temporal)
    - Knowledge Graph (Relations)
    """

    def __init__(self):
        self.db = DB()
        try: 
            self.db.init_db()
        except: 
            pass
        self.vector_store = LocalVectorStore()
        self.embedder = Embedder.get_instance()
        self.entity_extractor = EntityExtractor()

    def rehydrate(self, query: str, time_filter: Optional[str] = None, limit: int = 5) -> List[RankedChunk]:
        """
        Main entry point: Retrieve, Rank, Deduplicate.
        """
        candidates: List[RankedChunk] = []

        # 1. Vector Search (Base Retrieval)
        # ----------------------------------------------------------------
        query_vec = self.embedder.encode(query).tolist()
        where_clause = self._build_time_filter(time_filter)
        
        try:
            vec_chunks = self.vector_store.search(query_vec, limit=limit, where_clause=where_clause)
            if vec_chunks:
                for chk in vec_chunks:
                    # Score is currently not returned by LocalVectorStore search method on Chunk object
                    # We'll assume a default or we need to update search to return score?
                    # For now, default 0.8
                    score = 0.8 
                    
                    chunk = RankedChunk(
                        doc_hash=chk.doc_hash,
                        chunk_hash=chk.chunk_hash,
                        text=chk.text,
                        start_char=chk.start_char,
                        end_char=chk.end_char,
                        index=chk.index,
                        embedding=None,
                        category="note",
                        score=score,
                        boost_reason=f"vector:{score:.2f}",
                        source_signal="vector"
                    )
                    candidates.append(chunk)
        except Exception as e:
            # Vector store might be empty or error
            # print(f"Vector search error: {e}") # Debug
            pass

        # 2. Temporal Reinforcement
        # ----------------------------------------------------------------
        temporal_keywords = ["last week", "yesterday", "today", "meeting", "met", "who", "talk"]
        if any(k in query.lower() for k in temporal_keywords):
            cal_events = self._get_calendar_events(query)
            for event in cal_events:
                # Format Synthetic Text
                parts = json.loads(event['participants']) if isinstance(event['participants'], str) else event['participants']
                parts_str = ", ".join(parts) if parts else "Unknown"
                text = f"[Calendar Event] {event['start_time']}: {event['title']} (Participants: {parts_str})"

                chunk = RankedChunk(
                    doc_hash="calendar",
                    chunk_hash=f"cal_{event['event_id']}",
                    text=text,
                    start_char=0,
                    end_char=len(text),
                    category="calendar",
                    score=1.5, # Strong boost for explicit temporal relevance
                    boost_reason="temporal:explicit_match",
                    source_signal="calendar"
                )
                candidates.append(chunk)

        # 3. Entity Graph Expansion
        # ----------------------------------------------------------------
        entities = self.entity_extractor.extract(query)
        for entity in entities:
             edges = self.db.get_entity_edges(entity.name)
             for edge in edges:
                 # Check if this edge links to a chunk we already found? 
                 # Or bring in new ones.
                 
                 chunk = RankedChunk(
                     doc_hash=edge['doc_id'],
                     chunk_hash=edge['chunk_hash'],
                     text=f"[Related to {entity.name}] {edge['text']}",
                     start_char=0,
                     end_char=len(edge['text']),
                     category="entity_recall",
                     score=1.2, # Medium boost
                     boost_reason=f"entity:{entity.name}",
                     source_signal="entity"
                 )
                 candidates.append(chunk)

        # 4. Global Ranking & Deduplication
        # ----------------------------------------------------------------
        final_list = self._deduplicate_and_rank(candidates, limit)
        return final_list

    def _deduplicate_and_rank(self, candidates: List[RankedChunk], limit: int) -> List[RankedChunk]:
        """Merge candidates, keeping highest score for duplicates."""
        merged: Dict[str, RankedChunk] = {}
        
        for c in candidates:
            if c.chunk_hash in merged:
                # Keep highest score
                if c.score > merged[c.chunk_hash].score:
                    merged[c.chunk_hash] = c
                # If existing is vector and new is entity, maybe merge reasons?
                # For now, simple override.
            else:
                merged[c.chunk_hash] = c
                
        # Sort desc
        sorted_chunks = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return sorted_chunks[:limit]

    def _build_time_filter(self, time_filter: Optional[str]) -> Optional[str]:
        if not time_filter: return None
        now = datetime.now()
        if time_filter == "last_week":
            cutoff = now - timedelta(days=7)
            return f"timestamp >= '{cutoff.isoformat()}'"
        return None

    def _get_calendar_events(self, query: str) -> List[Dict]:
        # Reuse heuristic from SearchEngine (refactored here)
        start_date = None
        end_date = datetime.now()
        q = query.lower()
        if "last week" in q:
            start_date = end_date - timedelta(days=7)
        elif "yesterday" in q:
            start_date = end_date - timedelta(days=1)
            end_date = start_date + timedelta(days=1)
        elif "today" in q:
            start_date = end_date.replace(hour=0, minute=0)
        else:
            start_date = end_date - timedelta(days=30)
            
        return self.db.get_calendar_events(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=5
        )
