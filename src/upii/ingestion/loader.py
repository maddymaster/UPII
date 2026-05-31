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
            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    yield from self._process_file(full_path)
        else:
            yield from self._process_file(path)

    def _process_file(self, file_path: str) -> Generator[Document, None, None]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.pdf', '.txt', '.md', '.mbox']:
            return # Skip unsupported

        if ext == '.mbox':
             # Special handling for mbox (yields multiple docs)
             from upii.ambient.email_connector import EmailConnector
             for email_data in EmailConnector.parse_mbox(file_path):
                 if not email_data['content'].strip(): continue
                 
                 # Hash content for dedup
                 content_hash = hashlib.sha256(email_data['content'].encode('utf-8')).hexdigest()
                 
                 yield Document(
                    path=str(Path(file_path).resolve()), # We map all emails to the mbox file path? Or virtual path?
                    # Virtual path is better for pointing to specific email, but system expects real path.
                    # We stick to file path but the content is different.
                    content_hash=content_hash,
                    content=email_data['content'],
                    created_at=datetime.now(), # Ideally parse email_data['date']
                    source_type="email",
                    metadata={"sender": email_data['sender'], "subject": email_data['title']}
                 )
             return

        try:
            content_hash = self.compute_file_hash(file_path)
            content = self._extract_text(file_path, ext)
            
            if not content.strip():
                logger.warning(f"Empty content for {file_path}")
                return

            stats = os.stat(file_path)
            created_at = datetime.fromtimestamp(stats.st_ctime)
            
            yield Document(
                path=str(Path(file_path).resolve()),
                content_hash=content_hash,
                content=content,
                created_at=created_at,
                source_type=ext.replace('.', ''),
                metadata={"size": stats.st_size}
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
