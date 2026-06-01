import os
import time
import hashlib
import threading
from typing import Dict, Set, List, Tuple, Optional
from upii.core.logger import logger
from upii.core.concurrency import SafeRunner
from upii.ambient.sources import Source, registry
from upii.ingestion.loader import LocalLoader
from upii.core.types import Document

# Default polling cadence used ONLY when we fall back from watchdog.
POLLING_FALLBACK_INTERVAL = 5.0


class FileSystemSource(Source):
    """
    Robust file watcher with deduplication, debouncing, and delete handling.

    Primary backend is `watchdog` (native OS file-system events — near-zero idle
    CPU). If watchdog cannot be imported, or none of the watch paths can be
    scheduled (e.g. an unsupported network mount), it transparently falls back
    to a polling loop at POLLING_FALLBACK_INTERVAL.
    """
    def __init__(self):
        super().__init__("filesystem", "Monitors approved directories for changes.")
        self.watch_paths: List[str] = []
        # Cache: path -> (mtime, size, content_hash)
        self._cache: Dict[str, Tuple[float, int, str]] = {}
        self.poll_interval = 2.0
        self._interval_explicit = False
        # Skip files touched within this window (avoids capturing mid-write).
        self.debounce_seconds = 0.3
        self.loader = LocalLoader()
        # Which backend ended up active: "watchdog" | "polling" | None.
        self.backend: Optional[str] = None
        self.thread = None
        self._observer = None
        self._timers: Dict[str, threading.Timer] = {}
        self._timers_lock = threading.Lock()

    def configure(self, config: Dict):
        if "watch_paths" in config:
            self.watch_paths = config["watch_paths"]
        if "interval" in config:
            self.poll_interval = config["interval"]
            self._interval_explicit = True

    # -- lifecycle ----------------------------------------------------------

    def start(self):
        if self.is_running:
            return

        # Bug #2 fix: the running watcher must reflect paths approved via
        # `features.add_watch_path()` (persisted in features.yaml), merged with
        # any explicitly configured paths.
        try:
            from upii.core.features import features
            feat_paths = list(features.get_watch_paths())
        except Exception:
            feat_paths = []
        # Order-preserving union.
        self.watch_paths = list(dict.fromkeys([*self.watch_paths, *feat_paths]))

        if not self.watch_paths:
            logger.warning("FileSystemSource started with no paths.")

        self.is_running = True
        self.storage.init_db()

        if self._start_watchdog():
            self.backend = "watchdog"
        else:
            self.backend = "polling"
            if not self._interval_explicit:
                self.poll_interval = POLLING_FALLBACK_INTERVAL
            self.thread = SafeRunner.run_daemon(self._loop, name="FileSystemWatcher")

        logger.info(f"FileSystemSource started (backend={self.backend}).")

    def stop(self):
        self.is_running = False
        # Cancel any pending debounce timers.
        with self._timers_lock:
            for t in self._timers.values():
                try:
                    t.cancel()
                except Exception:
                    pass
            self._timers.clear()
        # Tear down the watchdog observer if active.
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception:
                pass
            self._observer = None
        # Join the polling thread if active.
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("FileSystemSource stopped.")

    # -- watchdog backend ---------------------------------------------------

    def _try_import_watchdog(self):
        """Import watchdog. Isolated so tests can monkeypatch it to simulate a
        missing dependency (and exercise the polling fallback)."""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        return Observer, FileSystemEventHandler

    def _start_watchdog(self) -> bool:
        try:
            Observer, FileSystemEventHandler = self._try_import_watchdog()
        except Exception as e:
            logger.warning(f"watchdog unavailable; falling back to polling: {e}")
            return False

        src = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    src._schedule_settle(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    src._schedule_settle(event.src_path)

            def on_moved(self, event):
                # A rename = delete(src) + create(dest).
                if not event.is_directory:
                    src._on_delete(event.src_path)
                    src._schedule_settle(event.dest_path)

            def on_deleted(self, event):
                if not event.is_directory:
                    src._on_delete(event.src_path)

        try:
            observer = Observer()
        except Exception as e:
            logger.warning(f"watchdog observer init failed; falling back: {e}")
            return False

        scheduled = 0
        for p in self.watch_paths:
            if os.path.isdir(p):
                try:
                    observer.schedule(_Handler(), p, recursive=True)
                    scheduled += 1
                except Exception as e:
                    # e.g. unsupported filesystem / network mount.
                    logger.warning(f"watchdog could not watch {p}: {e}")

        if scheduled == 0:
            return False

        try:
            observer.start()
        except Exception as e:
            logger.warning(f"watchdog observer start failed; falling back: {e}")
            return False

        self._observer = observer
        return True

    def _schedule_settle(self, path: str):
        """Debounce native events: coalesce a burst of writes into one capture
        once the file has been quiet for `debounce_seconds`."""
        if not self.is_running or not self._is_watchable(path):
            return
        with self._timers_lock:
            existing = self._timers.get(path)
            if existing:
                existing.cancel()
            timer = threading.Timer(self.debounce_seconds, self._settle, args=(path,))
            timer.daemon = True
            self._timers[path] = timer
            timer.start()

    def _settle(self, path: str):
        with self._timers_lock:
            self._timers.pop(path, None)
        if not self.is_running:
            return
        try:
            stat = os.stat(path)
        except OSError:
            return  # vanished before it settled
        cached = self._cache.get(path)
        if cached is None:
            self._handle_change(path, "created", stat.st_mtime, stat.st_size)
        else:
            self._handle_change(path, "modified", stat.st_mtime, stat.st_size, cached[2])

    def _on_delete(self, path: str):
        with self._timers_lock:
            t = self._timers.pop(path, None)
            if t:
                t.cancel()
        # Only emit a delete for files we had actually captured.
        if path in self._cache:
            self._handle_delete(path)
            del self._cache[path]

    # -- polling backend (fallback) ----------------------------------------

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
                    if not self._is_watchable(file):
                        continue

                    abs_path = os.path.join(root, file)
                    try:
                        stat = os.stat(abs_path)
                        # Debounce: skip if very recent
                        if (time.time() - stat.st_mtime) < self.debounce_seconds:
                            continue
                        current_files[abs_path] = (stat.st_mtime, stat.st_size)
                    except OSError:
                        pass  # File vanished during scan

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

    # -- shared capture logic ----------------------------------------------

    def _is_watchable(self, path: str) -> bool:
        """True if a path/filename is a candidate for capture."""
        name = os.path.basename(path)
        if name.startswith(('.', '~', '$')):
            return False
        return name.endswith(('.md', '.txt', '.pdf'))

    def _handle_change(self, path: str, type: str, mtime: float, size: int, old_hash: str = None):
        try:
            # Load doc directly to get hash + content for staging.
            doc_gen = self.loader.load(path)
            doc = next(doc_gen, None)

            if not doc:
                return  # Empty or unreadable

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
        # Record the delete event; we don't stage a doc (no content to promote).
        event_id = self.storage.add_event("deleted", path)
        self.storage.log_audit(self.name, "capture", {"path": path, "type": "deleted"})
        logger.debug(f"Recorded delete: {path}")


class PollingWatcher:
    """
    Foreground/daemon wrapper around FileSystemSource.

    Sources its watch paths from the FeatureFlags singleton (features.yaml),
    which is how `upii watch <path>` and the test-suite configure paths. This
    is the wire between features.add_watch_path() and the running source.

    (Name kept for API stability; the underlying source now prefers watchdog
    and only polls as a fallback.)
    """

    def __init__(self, interval: float = None):
        from upii.core.features import features

        self.source = FileSystemSource()
        cfg = {"watch_paths": list(features.get_watch_paths())}
        if interval is not None:
            cfg["interval"] = interval
        self.source.configure(cfg)

    @property
    def watch_paths(self) -> List[str]:
        return self.source.watch_paths

    @property
    def is_running(self) -> bool:
        return self.source.is_running

    @property
    def backend(self) -> Optional[str]:
        return self.source.backend

    def start(self):
        self.source.start()

    def stop(self):
        self.source.stop()


# Auto-register
# Note: In a real app we might avoid auto-register on import if import side-effects are bad,
# but for this structure it ensures one implementation exists.
fs_source = FileSystemSource()
registry.register(fs_source)
