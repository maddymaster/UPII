import os
import hashlib
from typing import Generator, Optional
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader
from upii.core.types import Document, ILoader
from upii.core.errors import IngestionError
import logging

logger = logging.getLogger(__name__)


def parse_frontmatter(content: str):
    """Split a leading YAML frontmatter block from markdown content.

    Returns (metadata: dict, body: str). If no `---`-delimited frontmatter is
    present, returns ({}, content) unchanged. Best-effort: a malformed block is
    treated as no frontmatter.
    """
    if not content.startswith("---"):
        return {}, content
    lines = content.splitlines()
    # First line must be exactly the opening fence.
    if lines[0].strip() != "---":
        return {}, content
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            try:
                import yaml
                meta = yaml.safe_load(block) or {}
                if not isinstance(meta, dict):
                    return {}, content
                return meta, body.lstrip("\n")
            except Exception:
                return {}, content
    return {}, content


class LocalLoader:
    """Handles loading and hashing of files."""

    def compute_file_hash(self, path: str) -> str:
        sha256 = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    sha256.update(data)
            return sha256.hexdigest()
        except OSError as e:
            raise IngestionError(f"Failed to read file for hashing {path}: {e}")

    def load(self, path: str) -> Generator[Document, None, None]:
        if not os.path.exists(path):
            logger.error(f"Path not found: {path}")
            return

        if os.path.isdir(path):
            # Deterministic traversal: sort subdirectories and files so ingest
            # order is a pure function of the tree, not of filesystem ordering.
            for root, dirs, files in os.walk(path):
                dirs.sort()
                for file in sorted(files):
                    full_path = os.path.join(root, file)
                    # A mailbox is never swept up by a directory ingest. It holds
                    # third-party correspondence, so it enters durable memory only
                    # when the user names the file explicitly.
                    if os.path.splitext(file)[1].lower() == '.mbox':
                        logger.info(
                            "Skipping mailbox %s: ingest mail by naming the file "
                            "explicitly (`upii ingest %s`).", full_path, full_path
                        )
                        continue
                    yield from self._process_file(full_path)
        else:
            yield from self._process_file(path)

    def _process_file(self, file_path: str) -> Generator[Document, None, None]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.pdf', '.txt', '.md', '.mbox']:
            return # Skip unsupported

        if ext == '.mbox':
            # A mailbox is a container of many documents, not one document, so each
            # message gets its own VIRTUAL path -- "<mbox>#<message-key>". The
            # incremental-ingest rules in ingestion/pipeline.py key on the path:
            # mapping every message to the mbox's own path made
            # same-path-different-hash look like an edit, so each message purged
            # the one before it and only the last survived.
            from upii.ambient.email_connector import EmailConnector
            mbox_path = str(Path(file_path).resolve())
            for email_data in EmailConnector.parse_mbox(file_path):
                content = email_data['content']
                if not content.strip():
                    continue

                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

                # Message identity, in preference order. A Message-ID is stable
                # across edits, so an edited message replaces its own prior
                # version. Falling back to the content hash keeps the path stable
                # when messages are reordered (an ordinal index would not), at the
                # cost of an edited message reading as a new one.
                msg_id = (email_data.get('email_id') or '').strip().strip('<>')
                msg_key = msg_id or content_hash[:16]

                yield Document(
                    path=f"{mbox_path}#{msg_key}",
                    content_hash=content_hash,
                    content=content,
                    created_at=datetime.now(),  # provenance, never part of a hash
                    source_type="email",
                    metadata={
                        "sender": email_data['sender'],
                        "subject": email_data['title'],
                        "mbox_path": mbox_path,
                    },
                )
            return

        try:
            content_hash = self.compute_file_hash(file_path)
            content = self._extract_text(file_path, ext)

            # Pull YAML frontmatter (e.g. `author:`) out of text formats.
            meta = {}
            if ext in ('.md', '.txt'):
                meta, content = parse_frontmatter(content)

            if not content.strip():
                logger.warning(f"Empty content for {file_path}")
                return

            stats = os.stat(file_path)
            created_at = datetime.fromtimestamp(stats.st_ctime)

            metadata = {"size": stats.st_size}
            metadata.update(meta)  # frontmatter keys (author, etc.) win

            yield Document(
                path=str(Path(file_path).resolve()),
                content_hash=content_hash,
                content=content,
                created_at=created_at,
                source_type=ext.replace('.', ''),
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            # We assume the caller handles logging, but we yield nothing
            
    def _extract_text(self, path: str, ext: str) -> str:
        if ext == '.pdf':
            try:
                reader = PdfReader(path)
                text = []
                for page in reader.pages:
                    text.append(page.extract_text() or "")
                return "\n".join(text)
            except Exception as e:
                raise IngestionError(f"PDF extract error: {e}")
        else:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except Exception as e:
                raise IngestionError(f"Text extract error: {e}")
