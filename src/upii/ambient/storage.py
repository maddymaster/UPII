import sqlite3
import json
import uuid
import os
from typing import Optional, Dict, List
from upii.core.config import config
from upii.core.logger import logger

class StagingDB:
    """Interface to the v1.0 Staging Database (Ambient)."""
    
    def __init__(self):
        self.db_path = config.staging_db_path
        
    def init_db(self):
        """Initialize staging schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        # Staging Docs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staging_docs (
                staging_id TEXT PRIMARY KEY,
                source_event_id TEXT,
                file_path TEXT NOT NULL,
                content_hash TEXT,
                parsed_content TEXT,
                metadata JSON,
                status TEXT DEFAULT 'review',
                FOREIGN KEY(source_event_id) REFERENCES events(event_id)
            )
        """)
        
        # Audit Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                action TEXT NOT NULL,         -- 'enable', 'disable', 'capture', 'error'
                details JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()

    def log_audit(self, source: str, action: str, details: Dict = {}):
        """Write an entry to the audit log."""
        audit_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs (audit_id, source_name, action, details) VALUES (?, ?, ?, ?)",
            (audit_id, source, action, json.dumps(details))
        )
        conn.commit()
        conn.close()
        return audit_id
        
    def get_audit_logs(self, limit: int = 50) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_event(self, event_type: str, file_path: str) -> str:
        """Log a raw file system event."""
        event_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (event_id, event_type, file_path) VALUES (?, ?, ?)",
            (event_id, event_type, file_path)
        )
        conn.commit()
        conn.close()
        return event_id

    def add_staging_doc(self, source_event_id: str, file_path: str, content: str, content_hash: str, metadata: Dict) -> str:
        """Add a parsed document to staging."""
        staging_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO staging_docs 
               (staging_id, source_event_id, file_path, content_hash, parsed_content, metadata) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (staging_id, source_event_id, file_path, content_hash, content, json.dumps(metadata))
        )
        conn.commit()
        conn.close()
        return staging_id
        
    def get_pending_events(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE status = 'pending' ORDER BY detected_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_events(self) -> List[Dict]:
        """Return every event regardless of status (pending/approved/rejected/acknowledged)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events ORDER BY detected_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_staging_doc_by_event(self, event_id: str) -> Optional[Dict]:
        """Fetch the staged (reviewed) document content for a given event.

        This is the content the operator approved — promotion must use this,
        NOT a fresh disk read, so what enters LTM is exactly what was reviewed.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM staging_docs WHERE source_event_id = ? LIMIT 1", (event_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_event_status(self, event_id: str, status: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE events SET status = ? WHERE event_id = ?", (status, event_id))
        conn.commit()
        conn.close()

    def update_staging_status(self, staging_id: str, status: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE staging_docs SET status = ? WHERE staging_id = ?", (status, staging_id))
        conn.commit()
        conn.close()
