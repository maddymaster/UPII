
import sqlite3
import datetime
import os
from typing import Dict, Any, Optional
from upii.core.config import config
from upii.core.logger import logger
from upii.storage.db import DB

class MetricsCollector:
    """
    Collects local-only usage metrics (telemetry).
    Data is stored in 'daily_metrics' table in upii.db.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricsCollector, cls).__new__(cls)
            cls._instance.db = DB()
        return cls._instance

    def _get_today_date(self) -> str:
        return datetime.date.today().isoformat()

    def _upsert_counter(self, column: str, increment: int = 1):
        """Generic upsert for counter columns."""
        today = self._get_today_date()
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            # Upsert: Try insert, if exists, update
            cursor.execute(
                f"""
                INSERT INTO daily_metrics (date, {column}) VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET {column} = {column} + ?
                """,
                (today, increment, increment)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")
        finally:
            conn.close()

    def track_query(self):
        """Record a user query."""
        self._upsert_counter("queries_count", 1)

    def track_explicit_ingest(self, count: int = 1):
        """Record explicit ingestion (CLI)."""
        self._upsert_counter("explicit_ingest_count", count)

    def track_passive_ingest(self, count: int = 1):
        """Record passive ingestion (Inbox promotion)."""
        self._upsert_counter("passive_ingest_count", count)

    def update_db_snapshot(self):
        """Snapshot DB size and doc count."""
        today = self._get_today_date()
        db_path = config.db_path
        size_mb = 0.0
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            
        conn = self.db.get_connection()
        try:
             cursor = conn.cursor()
             cursor.execute("SELECT COUNT(*) FROM documents")
             doc_count = cursor.fetchone()[0]
             
             cursor.execute(
                 """
                 INSERT INTO daily_metrics (date, total_docs_count, db_size_mb) VALUES (?, ?, ?)
                 ON CONFLICT(date) DO UPDATE SET 
                    total_docs_count = excluded.total_docs_count,
                    db_size_mb = excluded.db_size_mb
                 """,
                 (today, doc_count, size_mb)
             )
             conn.commit()
        except Exception as e:
            logger.error(f"Failed to snapshot metrics: {e}")
        finally:
            conn.close()

    def get_history(self, limit: int = 7) -> list[Dict[str, Any]]:
        """Retrieve recent metrics."""
        conn = self.db.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_metrics ORDER BY date DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def export_all(self) -> list[Dict[str, Any]]:
        """Export full history for user transparency."""
        conn = self.db.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_metrics ORDER BY date DESC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
