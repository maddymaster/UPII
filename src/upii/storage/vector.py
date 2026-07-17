import lancedb
import pyarrow as pa
from typing import List, Optional, Dict, Any
from datetime import datetime
from upii.core.config import config
from upii.core.types import Chunk
from upii.core.errors import StorageError

class LocalVectorStore:
    """Wrapper for LanceDB vector storage."""
    
    def __init__(self):
        self.db = lancedb.connect(config.vector_store_path)
        self.table_name = "vectors"
        
    def _get_table(self):
        try:
            return self.db.open_table(self.table_name)
        except Exception:
            # Table doesn't exist or other error
            return None

    def add(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        # Prepare data
        data = []
        for c in chunks:
            if c.embedding is None:
                continue # Skip chunks without embeddings
            
            data.append({
                "id": c.chunk_hash,
                "vector": c.embedding,
                "text": c.text,
                "doc_id": c.doc_hash,
                "timestamp": datetime.now().isoformat()
            })
            
        if not data:
            return

        try:
            table = self._get_table()
            if table is None:
                # Create
                self.db.create_table(self.table_name, data=data)
            else:
                table.add(data)
        except Exception as e:
            raise StorageError(f"LanceDB error: {e}")

    def delete(self, doc_hash: str) -> None:
        """Delete all vectors belonging to a document (by ``doc_id``).

        No-op if the table or rows do not exist. Used by edit/delete handling to
        keep the vector store in sync with the metadata store.
        """
        table = self._get_table()
        if table is None:
            return
        try:
            # Escape single quotes to keep the SQL predicate well-formed.
            safe = doc_hash.replace("'", "''")
            table.delete(f"doc_id = '{safe}'")
        except Exception as e:
            raise StorageError(f"LanceDB delete error: {e}")

    def delete_chunks(self, chunk_ids: List[str]) -> None:
        """Delete specific vectors by chunk id (``id`` column). No-op if empty."""
        if not chunk_ids:
            return
        table = self._get_table()
        if table is None:
            return
        try:
            quoted = ",".join("'" + c.replace("'", "''") + "'" for c in chunk_ids)
            table.delete(f"id IN ({quoted})")
        except Exception as e:
            raise StorageError(f"LanceDB delete error: {e}")

    def search(self, query_vec: List[float], limit: int = 5, where_clause: Optional[str] = None) -> List[Chunk]:
        table = self._get_table()
        if table is None:
            return []
            
        try:
            query = table.search(query_vec).limit(limit)
            if where_clause:
                query = query.where(where_clause)
            
            # to_list() (dicts) rather than to_pandas() so pandas is not a runtime
            # dependency — it is heavy and was never declared, so a clean install
            # would hit "No module named 'pandas'" the first time anyone searched.
            chunks = []
            for row in query.to_list():
                # Reconstruct partial chunk
                chunks.append(Chunk(
                    doc_hash=row['doc_id'],
                    chunk_hash=row['id'],
                    text=row['text'],
                    start_char=0, # Lost in vector store, usually look up in DB if needed
                    end_char=0,
                    embedding=None # Don't return vector
                ))
            return chunks
        except Exception as e:
            raise StorageError(f"LanceDB search error: {e}")
    def search_scored(
        self, query_vec: List[float], limit: int = 5, where_clause: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Like :meth:`search` but keeps the similarity distance and timestamp.

        Returns a list of ``{"chunk": Chunk, "distance": float, "timestamp": str}``
        ordered by ascending distance (most similar first). ``distance`` is the raw
        LanceDB metric (L2 by default); the caller converts it to a similarity. The
        rehydrator needs the distance for the *semantic* signal and the ingest
        timestamp for the *temporal* recency signal, both of which the plain
        :meth:`search` discards.
        """
        table = self._get_table()
        if table is None:
            return []
        try:
            query = table.search(query_vec).limit(limit)
            if where_clause:
                query = query.where(where_clause)
            out: List[Dict[str, Any]] = []
            for row in query.to_list():  # dicts, no pandas dependency
                dist = row.get("_distance")
                out.append(
                    {
                        "chunk": Chunk(
                            doc_hash=row["doc_id"],
                            chunk_hash=row["id"],
                            text=row["text"],
                            start_char=0,
                            end_char=0,
                            embedding=None,
                        ),
                        "distance": float(dist) if dist is not None else None,
                        "timestamp": row.get("timestamp"),
                    }
                )
            return out
        except Exception as e:
            raise StorageError(f"LanceDB search error: {e}")

    def count(self) -> int:
        table = self._get_table()
        if table is None:
            return 0
        return len(table)

    def get_stats(self) -> Dict[str, Any]:
        table = self._get_table()
        if table is None:
            return {"count": 0, "last_ingest": None}
        
        # LanceDB specific way to get last modified or max timestamp?
        # For simplicity in v0.5, we rely on count. Timestamp query might be slow.
        return {
            "count": len(table)
        }
