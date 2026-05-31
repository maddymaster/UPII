import os
import time
import hashlib
from typing import Dict, Set, List, Tuple
from upii.core.logger import logger
from upii.core.concurrency import SafeRunner
from upii.ambient.sources import Source, registry
from upii.ingestion.loader import LocalLoader
from upii.core.types import Document

class FileSystemSource(Source):
    """
    Robust file watcher with deduplication, debouncing, and delete handling.
    """
    def __init__(self):
        super().__init__("filesystem", "Monitors approved directories for changes.")
        self.watch_paths: List[str] = []
        # Cache: path -> (mtime, size, content_hash)
        self._cache: Dict[str, Tuple[float, int, str]] = {}
        self.poll_interval = 2.0
        self.debounce_seconds = 1.0
        self.loader = LocalLoader()

    def configure(self, config: Dict):
        if "watch_paths" in config:
            self.watch_paths = config["watch_paths"]
        if "interval" in config:
            self.poll_interval = config["interval"]

    def start(self):
        if self.is_running:
            return
        if not self.watch_paths:
            logger.warning("FileSystemSource started with no paths.")
            
        self.is_running = True
        self.storage.init_db()
        self.thread = SafeRunner.run_daemon(self._loop, name="FileSystemWatcher")
        logger.info("FileSystemSource started.")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("FileSystemSource stopped.")

    def _loop(self):
        while self.is_running:
            if not self.watch_paths:
                time.sleep(self.poll_interval)
                continue

            try:
                self._run_scan_cycle()
            except Exception as e:
                logger.error(f"Error in watcher cycle: {e}")
                self.storage.log_audit(self.name, "error", {"error": str(e)})
            
            time.sleep(self.poll_interval)

    def _run_scan_cycle(self):
        # 1. Snapshot current disk state
        current_files: Dict[str, Tuple[float, int]] = {}
        
        for root_path in self.watch_paths:
            if not os.path.exists(root_path):
                continue
                
            for root, _, files in os.walk(root_path):
                for file in files:
                    # Filter system/temp files
                    if file.startswith(('.', '~', '$')): continue
                    if not file.endswith(('.md', '.txt', '.pdf')): continue
                    
                    abs_path = os.path.join(root, file)
                    try:
                        stat = os.stat(abs_path)
                        # Debounce: skip if very recent
                        if (time.time() - stat.st_mtime) < self.debounce_seconds:
                            continue
                        current_files[abs_path] = (stat.st_mtime, stat.st_size)
                    except OSError:
                        pass # File vanished during scan

        # 2. Detect Changes
        # DELETES: In cache but not on disk
        deleted_paths = set(self._cache.keys()) - set(current_files.keys())
        for path in deleted_paths:
            self._handle_delete(path)
            del self._cache[path]

        # ADDS & MODS
        for path, (mtime, size) in current_files.items():
            cached = self._cache.get(path)
            
            if not cached:
                # NEW
                self._handle_change(path, "created", mtime, size)
            else:
                old_mtime, old_size, old_hash = cached
                if mtime > old_mtime or size != old_size:
                    # MODIFIED
                    self._handle_change(path, "modified", mtime, size, old_hash)

    def _handle_change(self, path: str, type: str, mtime: float, size: int, old_hash: str = None):
        try:
            # Hash content to check real change
            # LocalLoader handles reading. We just need hash first or load doc.
            # Let's load doc directly to get hash + content for staging
            doc_gen = self.loader.load(path)
            doc = next(doc_gen, None)
            
            if not doc:
                return # Empty or unreadable

            if old_hash and doc.content_hash == old_hash:
                # False alarm (touched but content same)
                self._cache[path] = (mtime, size, old_hash)
                return

            # Update cache
            self._cache[path] = (mtime, size, doc.content_hash)

            # Stage it
            event_id = self.storage.add_event(type, path)
            self.storage.add_staging_doc(event_id, path, doc.content, doc.content_hash, doc.metadata)
            
            self.storage.log_audit(self.name, "capture", {
                "path": path, 
                "type": type,
                "hash": doc.content_hash[:8]
            })
            logger.debug(f"Staged {type}: {path}")
            
        except Exception as e:
            logger.error(f"Failed to stage {path}: {e}")

    def _handle_delete(self, path: str):
        # We record the delete event, but we don't 'stage' a doc.
        # Ideally we might stage a 'tombstone' or just log it.
        # User requirement: "Graceful handling of file deletes"
        event_id = self.storage.add_event("deleted", path)
        self.storage.log_audit(self.name, "capture", {"path": path, "type": "deleted"})
        logger.debug(f"Recorded delete: {path}")

# Auto-register
# Note: In a real app we might avoid auto-register on import if import side-effects are bad,
# but for this structure it ensures one implementation exists.
fs_source = FileSystemSource()
registry.register(fs_source)
