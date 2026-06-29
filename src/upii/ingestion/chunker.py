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

            # Content-addressed chunk id: a pure function of (chunk text, chunker
            # config) ONLY. It deliberately excludes the whole-file content hash and
            # the index so that an edit elsewhere in the file leaves an unchanged
            # chunk's hash stable (T1.2 "re-chunk only changed chunks"), and so the
            # same text under the same config always yields the same id.
            chunk_hash_input = f"{self.chunk_size}:{self.overlap}:{chunk_text}"
            chunk_id = hashlib.sha256(chunk_hash_input.encode("utf-8")).hexdigest()
            
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
