import sqlite3
import json
import uuid
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime
from upii.core.config import config
from upii.core.types import Document, Chunk, Task
from upii.core.errors import StorageError

class DB:
    """SQLite wrapper for metadata storage."""
    
    def __init__(self):
        self.path = config.db_path
    
    def get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def init_db(self):
        """Initialize tables based on data model."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Schema definition from data_model.md
        schema = [
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                source_type TEXT NOT NULL,
                created_at DATETIME,
                modified_at DATETIME,
                ingestion_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT NOT NULL UNIQUE,
                metadata JSON
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(content_hash);",
            "CREATE INDEX IF NOT EXISTS idx_docs_path ON documents(source_path);",
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                token_count INTEGER,
                start_offset INTEGER,
                end_offset INTEGER,
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);",
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                source_chunk_id TEXT,
                source_doc_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
            # Calendar Events (Temporal Memory)
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                event_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                participants JSON,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_time);",
            # Entity Knowledge Graph
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, category)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS entity_edges (
                edge_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                chunk_hash TEXT NOT NULL,
                source_doc_id TEXT NOT NULL,
                confidence REAL,
                context TEXT,
                FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_edges_entity ON entity_edges(entity_id);",
            "CREATE INDEX IF NOT EXISTS idx_edges_chunk ON entity_edges(chunk_hash);",
            # Metrics - Local Telemetry
            """
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date DATE PRIMARY KEY,
                queries_count INTEGER DEFAULT 0,
                explicit_ingest_count INTEGER DEFAULT 0,
                passive_ingest_count INTEGER DEFAULT 0,
                total_docs_count INTEGER DEFAULT 0,
                db_size_mb REAL DEFAULT 0.0
            );
            """
        ]
        
        try:
            for statement in schema:
                cursor.execute(statement)
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to init DB: {e}")
        finally:
            conn.close()

    def get_document_by_hash(self, content_hash: str) -> Optional[Document]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE content_hash = ?", (content_hash,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Document(
                path=row['source_path'],
                content_hash=row['content_hash'],
                content="", # We don't load full content here usually
                created_at=row['created_at'], # Need parsing strings back to datetime in real app if strictly typed
                metadata=json.loads(row['metadata']) if row['metadata'] else {},
                source_type=row['source_type']
            )
        return None

    def upsert_document(self, doc: Document, doc_id: str) -> str:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                INSERT INTO documents (doc_id, source_path, source_type, created_at, content_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(content_hash) DO UPDATE SET
                    source_path=excluded.source_path,
                    modified_at=CURRENT_TIMESTAMP
                """,
                (
                    doc_id,
                    doc.path,
                    doc.source_type,
                    doc.created_at,
                    doc.content_hash,
                    json.dumps(doc.metadata)
                )
            )
            conn.commit()
            return doc_id
        except sqlite3.Error as e:
            raise StorageError(f"Failed to upsert document: {e}")
        finally:
            conn.close()

    def add_chunks(self, chunks: List[Chunk]):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Revert to standard insert without category column
            data_standard = [
                (c.chunk_hash, c.doc_hash, c.index, c.text, 0, c.start_char, c.end_char) 
                for c in chunks
            ]

            cursor.executemany(
                """
                INSERT OR REPLACE INTO chunks (chunk_id, doc_id, chunk_index, text, token_count, start_offset, end_offset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                data_standard
            )
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to add chunks: {e}")
        finally:
            conn.close()

    def get_documents_by_path(self, source_path: str) -> List[Dict[str, str]]:
        """Return [{doc_id, content_hash}] for every document stored at a path.

        Used by the edit path: a changed file keeps its ``source_path`` but gets a
        new ``content_hash``, so we look up prior versions by path to clean them up.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT doc_id, content_hash FROM documents WHERE source_path = ?",
                (source_path,),
            )
            return [
                {"doc_id": row["doc_id"], "content_hash": row["content_hash"]}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_chunk_ids_for_doc(self, doc_id: str) -> List[str]:
        """Return the chunk ids belonging to a document."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT chunk_id FROM chunks WHERE doc_id = ?", (doc_id,))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_document(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Remove a document and everything anchored to it, by content hash.

        Deletes the document row, its chunks, and any entity edges / tasks that
        referenced it. (FK cascades are not enabled per-connection, so we delete
        explicitly.) Returns ``{"doc_id", "chunk_ids"}`` so the caller can purge the
        matching vectors, or ``None`` if no such document exists.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT doc_id FROM documents WHERE content_hash = ?", (content_hash,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            doc_id = row["doc_id"]

            cursor.execute("SELECT chunk_id FROM chunks WHERE doc_id = ?", (doc_id,))
            chunk_ids = [r[0] for r in cursor.fetchall()]

            cursor.execute("DELETE FROM entity_edges WHERE source_doc_id = ?", (doc_id,))
            cursor.execute("DELETE FROM tasks WHERE source_doc_id = ?", (doc_id,))
            cursor.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            cursor.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()
            return {"doc_id": doc_id, "chunk_ids": chunk_ids}
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete document: {e}")
        finally:
            conn.close()

    def get_chunks_by_author(self, author: str, limit: int = 3) -> List[str]:
        """Return chunk texts from documents whose metadata.author == author.

        Used by `write` to ground tone/style in the user's own writing.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT c.text AS text
                FROM chunks c
                JOIN documents d ON c.doc_id = d.doc_id
                WHERE json_extract(d.metadata, '$.author') = ?
                ORDER BY d.ingestion_time DESC
                LIMIT ?
                """,
                (author, limit),
            )
            return [row['text'] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    def add_tasks(self, tasks: List[Task]):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            data = [
                (t.task_id, t.description, t.status, t.source_chunk_id, t.source_doc_id)
                for t in tasks
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO tasks (task_id, description, status, source_chunk_id, source_doc_id) VALUES (?, ?, ?, ?, ?)",
                data
            )
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to add tasks: {e}")
        finally:
            conn.close()

    def get_tasks(self, status: Optional[str] = None, search: Optional[str] = None) -> List[Task]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM tasks"
        params = []
        conditions = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search:
            conditions.append("description LIKE ?")
            params.append(f"%{search}%")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Task(
                task_id=row['task_id'],
                description=row['description'],
                status=row['status'],
                source_chunk_id=row['source_chunk_id'],
                source_doc_id=row['source_doc_id'],
                created_at=row['created_at']
            )
            for row in rows
        ]
    
    def update_task_status(self, task_id: str, status: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id))
        conn.commit()
        conn.close()
        
    def add_calendar_event(self, event: Dict) -> str:
        """Add a calendar event."""
        event_id = event.get("event_id", str(uuid.uuid4()))
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT OR REPLACE INTO calendar_events 
                   (event_id, title, start_time, end_time, participants, source_file)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    event_id, 
                    event["title"], 
                    event["start_time"], 
                    event["end_time"], 
                    json.dumps(event.get("participants", [])),
                    event.get("source_file", "")
                )
            )
            conn.commit()
            return event_id
        finally:
            conn.close()

    def get_calendar_events(self, start_date: str = None, end_date: str = None, limit: int = 10) -> List[Dict]:
        """Query calendar events by time range."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            query = "SELECT * FROM calendar_events WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date)
            if end_date:
                query += " AND start_time <= ?"
                params.append(end_date)
                
            query += " ORDER BY start_time DESC LIMIT ?"
            params.append(limit)
            
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _entity_id(name: str, category: str) -> str:
        """Content-addressed entity id, so the same (name, category) always maps to
        the same id and an independent re-ingest of a corpus reproduces the same
        graph (upholds the 'same input -> same store' property)."""
        return hashlib.sha1(f"{name}\0{category}".encode("utf-8")).hexdigest()[:16]

    def add_entity(self, name: str, category: str) -> str:
        """Add or retrieve an entity. Idempotent; id is content-addressed."""
        entity_id = self._entity_id(name, category)
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO entities (entity_id, name, category) VALUES (?, ?, ?)",
                (entity_id, name, category),
            )
            conn.commit()
            return entity_id
        finally:
            conn.close()

    def write_entities_for_doc(self, doc_id: str, mentions) -> int:
        """(Re)write the entity nodes + chunk edges for one document, idempotently.

        ``mentions`` is an iterable of ``(name, category, chunk_hash, context)``.
        Existing edges for ``doc_id`` are deleted first, so a forced re-ingest does
        not duplicate them; entity and edge ids are content-addressed, so re-writing
        identical mentions converges to the identical rows. Returns the edge count.

        Entity extraction never feeds a chunk hash, so this does not affect the
        determinism/reproducibility of chunking.
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM entity_edges WHERE source_doc_id = ?", (doc_id,))
            n = 0
            for name, category, chunk_hash, context in mentions:
                eid = self._entity_id(name, category)
                cur.execute(
                    "INSERT OR IGNORE INTO entities (entity_id, name, category) VALUES (?, ?, ?)",
                    (eid, name, category),
                )
                edge_id = hashlib.sha1(f"{eid}\0{chunk_hash}".encode("utf-8")).hexdigest()[:16]
                cur.execute(
                    """INSERT OR IGNORE INTO entity_edges
                       (edge_id, entity_id, chunk_hash, source_doc_id, context, confidence)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (edge_id, eid, chunk_hash, doc_id, context, 1.0),
                )
                n += 1
            conn.commit()
            return n
        finally:
            conn.close()

    def add_entity_edge(self, entity_id: str, chunk_hash: str, source_doc_id: str, context: str, confidence: float = 1.0):
        """Link an entity to a chunk."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            edge_id = str(uuid.uuid4())
            cur.execute(
                """INSERT INTO entity_edges (edge_id, entity_id, chunk_hash, source_doc_id, context, confidence)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (edge_id, entity_id, chunk_hash, source_doc_id, context, confidence)
            )
            conn.commit()
        finally:
            conn.close()

    def get_entity_edges(self, entity_name: str) -> List[Dict]:
        """Retrieve chunks linked to an entity name."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            # Resolve the entity id. The extractor yields bare names ("Omega",
            # "Secret") while the graph often stores fuller names ("Project Omega",
            # "Project Secret"), so fall back to a substring match when the exact
            # name misses — otherwise the relational signal never fires in practice.
            cur.execute("SELECT entity_id FROM entities WHERE name = ?", (entity_name,))
            rows = cur.fetchall()
            if not rows and entity_name:
                cur.execute(
                    "SELECT entity_id FROM entities WHERE name LIKE ?",
                    (f"%{entity_name}%",),
                )
                rows = cur.fetchall()
            if not rows:
                return []
            
            entity_ids = [row['entity_id'] for row in rows]
            placeholders = ','.join('?' for _ in entity_ids)
            
            # LEFT JOIN so an edge is returned even when its chunk row is absent
            # (e.g. the source was removed, or the edge points at synthetic text).
            # Fall back to the edge's own stored ``context`` for the text, and to
            # ``source_doc_id`` for the doc, so the relational signal never silently
            # loses an edge to an INNER JOIN.
            query = f"""
                SELECT e.chunk_hash,
                       e.context,
                       e.source_doc_id,
                       e.confidence,
                       c.text AS chunk_text,
                       c.doc_id AS chunk_doc_id
                FROM entity_edges e
                LEFT JOIN chunks c ON e.chunk_hash = c.chunk_id
                WHERE e.entity_id IN ({placeholders})
            """
            cur.execute(query, entity_ids)
            rows = []
            for row in cur.fetchall():
                d = dict(row)
                rows.append(
                    {
                        "chunk_hash": d["chunk_hash"],
                        "context": d["context"],
                        "text": d["chunk_text"] if d["chunk_text"] is not None else d["context"],
                        "doc_id": d["chunk_doc_id"] if d["chunk_doc_id"] is not None else d["source_doc_id"],
                        "confidence": d["confidence"] if d["confidence"] is not None else 1.0,
                    }
                )
            return rows
        finally:
            conn.close()

    def get_entities(self) -> List[Dict[str, Any]]:
        """Return every entity as ``{entity_id, name, category, degree}``.

        ``degree`` is the number of chunk edges anchored to the entity — used to
        size nodes in the knowledge-graph visualisation.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT e.entity_id, e.name, e.category,
                       COUNT(ed.edge_id) AS degree
                FROM entities e
                LEFT JOIN entity_edges ed ON ed.entity_id = e.entity_id
                GROUP BY e.entity_id, e.name, e.category
                ORDER BY e.category, e.name
                """
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_cooccurrence_edges(self) -> List[Dict[str, Any]]:
        """Return entity-entity co-occurrence edges as ``{source, target, weight}``.

        Two entities co-occur when their edges point at the same ``chunk_hash``;
        the ``weight`` is the number of distinct chunks in which both appear. Only
        unordered pairs (``source < target``) are returned so each edge is unique.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.entity_id AS source,
                       b.entity_id AS target,
                       COUNT(DISTINCT a.chunk_hash) AS weight
                FROM entity_edges a
                JOIN entity_edges b
                  ON a.chunk_hash = b.chunk_hash
                 AND a.entity_id < b.entity_id
                GROUP BY a.entity_id, b.entity_id
                """
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def wipe_entities(self):
        """Clear all entity data (Reversible action)."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM entity_edges")
            cur.execute("DELETE FROM entities")
            conn.commit()
        finally:
            conn.close()
