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

    def search(self, query_vec: List[float], limit: int = 5, where_clause: Optional[str] = None) -> List[Chunk]:
        table = self._get_table()
        if table is None:
            return []
            
        try:
            query = table.search(query_vec).limit(limit)
            if where_clause:
                query = query.where(where_clause)
            
            results = query.to_pandas()
            chunks = []
            for _, row in results.iterrows():
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
