from typing import List, Optional, Generator, Protocol, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class Document:
    path: str
    content_hash: str
    content: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_type: str = "unknown"
    doc_id: Optional[str] = None

@dataclass
class Chunk:
    doc_hash: str # Reference to Document.doc_id (UUID)
    chunk_hash: str # Content deterministic hash
    text: str
    start_char: int
    end_char: int
    index: int = 0
    embedding: Optional[List[float]] = None
    category: str = "note" # note, decision, task

@dataclass
class RankedChunk(Chunk):
    score: float = 0.0
    boost_reason: str = ""
    source_signal: str = "vector" # vector, calendar, entity

@dataclass
class Task:
    task_id: str
    description: str
    status: str = "pending"
    source_chunk_id: str = ""
    source_doc_id: str = ""
    created_at: str = ""
    index: int = 0

class ILoader(Protocol):
    def load(self, path: str) -> Generator[Document, None, None]: ...

class IChunker(Protocol):
    def chunk(self, doc: Document) -> List[Chunk]: ...

class IVectorStore(Protocol):
    def add(self, chunks: List[Chunk]) -> None: ...
    def search(self, query_vec: List[float], limit: int = 5) -> List[Chunk]: ...
    def delete(self, doc_hash: str) -> None: ...

class IMetadataStore(Protocol):
    def exists(self, doc_hash: str) -> bool: ...
    def add_doc(self, doc: Document) -> None: ...
    def add_chunks(self, chunks: List[Chunk]) -> None: ...
    def get_chunks_by_hash(self, chunk_hashes: List[str]) -> List[Chunk]: ...

class ILocalLLM(Protocol):
    def generate(self, prompt: str, context: str) -> str: ...
