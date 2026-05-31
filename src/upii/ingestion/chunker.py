import hashlib
from typing import List
from upii.core.types import Document, Chunk
from upii.core.config import config

class RecursiveChunker:
    """Deterministic chunking strategy."""
    
    def __init__(self, chunk_size: int = config.chunk_size, overlap: int = config.chunk_overlap):
        self.chunk_size = chunk_size
        self.overlap = overlap
        
    def chunk(self, doc: Document) -> List[Chunk]:
        text = doc.content
        chunks = []
        
        # Simple sliding window for now (Robust enough for v0.5)
        # TODO: Implement actual recursive splitting by delimiters for v1
        
        start = 0
        text_len = len(text)
        idx = 0
        
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_text = text[start:end]
            
            # Deterministic ID: hash(doc_hash + index + text)
            # Including text ensures if we change chunking logic, ID changes
            chunk_hash_input = f"{doc.content_hash}-{idx}-{chunk_text}"
            chunk_id = hashlib.sha256(chunk_hash_input.encode()).hexdigest()
            
            chunks.append(Chunk(
                doc_hash=doc.doc_id if hasattr(doc, 'doc_id') else doc.content_hash, # Link to parent UUID or Hash
                chunk_hash=chunk_id,
                text=chunk_text,
                start_char=start,
                end_char=end,
                index=idx,
                embedding=None
            ))
            
            start += (self.chunk_size - self.overlap)
            idx += 1
            
        return chunks
