"""Approval inbox: promote or reject staged ambient captures.

Shared by ``upii inbox`` and the HTTP API so both apply exactly the same consent
rules. Nothing here prints; callers turn the returned outcome into CLI output or
an HTTP response.
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from upii.ambient.storage import StagingDB
from upii.core.types import Document

# Outcomes. Approve: APPROVED, ALREADY_APPROVED, WAS_REJECTED, DELETION_ACKNOWLEDGED,
# NO_CONTENT. Reject: REJECTED, ALREADY_REJECTED, WAS_APPROVED.
APPROVED = "approved"
ALREADY_APPROVED = "already_approved"
WAS_REJECTED = "was_rejected"
DELETION_ACKNOWLEDGED = "deletion_acknowledged"
NO_CONTENT = "no_content"
REJECTED = "rejected"
ALREADY_REJECTED = "already_rejected"
WAS_APPROVED = "was_approved"


@dataclass
class InboxResult:
    outcome: str
    event: Dict
    chunks: int = 0
    tasks: int = 0
    content_hash: Optional[str] = None


def find_event(stg: StagingDB, event_id: str, *, exact: bool = False) -> Optional[Dict]:
    """Look an event up among ALL events (so re-approving is an idempotent no-op).
    The CLI accepts an id prefix; the API requires the full id (``exact=True``)."""
    for e in stg.get_all_events():
        if (e["event_id"] == event_id) if exact else e["event_id"].startswith(event_id):
            return e
    return None


def approve_event(stg: StagingDB, target: Dict) -> InboxResult:
    """Promote the staged content of ``target`` into long-term memory."""
    if target["status"] == "approved":
        return InboxResult(ALREADY_APPROVED, target)
    if target["status"] == "rejected":
        return InboxResult(WAS_REJECTED, target)

    # Deleted events carry no content to promote.
    if target["event_type"] == "deleted":
        stg.update_event_status(target["event_id"], "acknowledged")
        stg.log_audit("inbox", "acknowledge", {"event_id": target["event_id"], "reason": "deletion event"})
        return InboxResult(DELETION_ACKNOWLEDGED, target)

    # Pull the PINNED staged content the operator reviewed — not a fresh disk read.
    sdoc = stg.get_staging_doc_by_event(target["event_id"])
    if not sdoc or not (sdoc.get("parsed_content") or "").strip():
        stg.update_event_status(target["event_id"], "acknowledged")
        return InboxResult(NO_CONTENT, target)

    from upii.analysis.embeddings import Embedder
    from upii.analysis.nlp import TaskExtractor
    from upii.ingestion.chunker import RecursiveChunker
    from upii.ingestion.pipeline import ingest_document
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore

    db = DB()
    try:
        db.init_db()
    except Exception:
        pass

    # Reconstruct the Document from the staged record.
    try:
        metadata = json.loads(sdoc.get("metadata") or "{}")
    except Exception:
        metadata = {}
    ext = os.path.splitext(sdoc["file_path"])[1].lower().replace(".", "") or "note"
    doc = Document(
        path=sdoc["file_path"],
        content_hash=sdoc["content_hash"],
        content=sdoc["parsed_content"],
        created_at=datetime.now(),
        source_type=ext,
        metadata=metadata,
    )

    # Promote to LTM via the shared deterministic pipeline (dedup + edit cleanup).
    result = ingest_document(doc, db, LocalVectorStore(), Embedder(), RecursiveChunker())
    chunks = result.chunks or []

    # Extract tasks, same as explicit ingest, so the auto-task beat works for ambient too.
    tasks = TaskExtractor().extract(chunks)
    if tasks:
        db.add_tasks(tasks)

    stg.update_event_status(target["event_id"], "approved")
    if sdoc.get("staging_id"):
        stg.update_staging_status(sdoc["staging_id"], "approved")
    stg.log_audit("inbox", "approve", {
        "event_id": target["event_id"],
        "file_path": sdoc["file_path"],
        "chunks": len(chunks),
        "tasks": len(tasks),
    })

    try:
        from upii.analysis.metrics import MetricsCollector
        MetricsCollector().track_passive_ingest(1)
    except Exception:
        pass
    return InboxResult(APPROVED, target, chunks=len(chunks), tasks=len(tasks),
                       content_hash=sdoc["content_hash"])


def reject_event(stg: StagingDB, target: Dict) -> InboxResult:
    """Mark ``target`` rejected. Rows are kept: the audit trail must survive."""
    if target["status"] == "rejected":
        return InboxResult(ALREADY_REJECTED, target)
    if target["status"] == "approved":
        return InboxResult(WAS_APPROVED, target)

    stg.update_event_status(target["event_id"], "rejected")
    sdoc = stg.get_staging_doc_by_event(target["event_id"])
    if sdoc and sdoc.get("staging_id"):
        stg.update_staging_status(sdoc["staging_id"], "rejected")
    stg.log_audit("inbox", "reject", {
        "event_id": target["event_id"],
        "file_path": target["file_path"],
    })
    return InboxResult(REJECTED, target)


def list_pending(stg: StagingDB) -> List[Dict]:
    """Pending captures with their staged content hash (``None`` for deletions)."""
    out = []
    for e in stg.get_pending_events():
        sdoc = stg.get_staging_doc_by_event(e["event_id"])
        out.append({**e, "content_hash": sdoc.get("content_hash") if sdoc else None})
    return out
