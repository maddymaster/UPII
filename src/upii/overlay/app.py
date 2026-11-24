
import ipaddress
import logging
import os
import re
import sys
import threading
from typing import Callable, Optional
from urllib.parse import urlsplit

try:
    import webview
except ImportError:
    webview = None

from upii.analysis.rehydration import ContextRehydrator
from upii.analysis.llm import NOT_FOUND_MESSAGE, LocalLLM
from upii.core.config import config
from upii.core.types import RankedChunk

logger = logging.getLogger("upii.overlay")

CHECK_DELAY = 0.6  # seconds between asking pywebview to hide/show and checking the window

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UPII Overlay</title>
    <style>
        body {
            background-color: transparent;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #eee;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            height: 100vh;
        }

        #app-container {
            margin-top: 15vh;
            width: 700px;
            background: rgba(22, 22, 24, 0.97);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        #search-box {
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        #input-field {
            width: 100%;
            background: transparent;
            border: none;
            font-size: 24px;
            color: white;
            outline: none;
            font-weight: 300;
        }
        
        #input-field::placeholder {
            color: rgba(255, 255, 255, 0.3);
        }

        #results-area {
            max-height: 500px;
            overflow-y: auto;
            padding: 20px;
            display: none; /* Hidden until search */
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: rgba(255, 255, 255, 0.5);
        }

        .answer-block {
            margin-bottom: 12px;
            line-height: 1.6;
            font-size: 18px;
            color: #f5f5f5;
        }

        .answered-main {
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
        }

        .answered-detail {
            margin-top: 2px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .sources-list {
            margin-top: 16px;
            font-size: 14px;
            color: rgba(255, 255, 255, 0.85);
        }

        .source-item {
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.12);
        }

        .source-path {
            color: #ffffff;
        }

        .source-excerpt {
            margin-top: 2px;
            font-size: 13px;
            line-height: 1.45;
            color: rgba(255, 255, 255, 0.75);
        }

    </style>
</head>
<body>
    <div id="app-container">
        <div id="search-box">
            <input type="text" id="input-field" placeholder="Ask UPII..." autocomplete="off">
        </div>
        <div id="results-area"></div>
    </div>

    <script>
        const input = document.getElementById('input-field');
        const results = document.getElementById('results-area');
        let debounceTimer;

        // Auto Focus
        window.onload = () => input.focus();

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                performSearch(input.value);
            }
            if (e.key === 'Escape') {
                pywebview.api.hide_window();
            }
        });

        async function performSearch(query) {
            if (!query.trim()) return;
            
            results.style.display = 'block';
            results.innerHTML = '<div class="loading">Thinking...</div>';
            
            try {
                // Call Python API
                const response = await pywebview.api.query(query);
                renderResponse(response);
            } catch (err) {
                results.innerHTML = `<div style="color:red">Error: ${err}</div>`;
            }
        }

        function esc(s) {
            const d = document.createElement('div');
            d.textContent = (s === null || s === undefined) ? '' : String(s);
            return d.innerHTML;
        }

        function escAttr(s) {
            return esc(s).replace(/"/g, '&quot;');
        }

        function renderResponse(data) {
            if (data.error) {
                results.innerHTML = `<div style="color:red">${esc(data.error)}</div>`;
                return;
            }

            let html = `<div class="answer-block">${esc(data.answer).replace(/\\n/g, '<br>')}</div>`;
            if (data.answered) {
                html += `<div class="answered-main">${esc(data.answered.main)}</div>`;
                html += `<div class="answered-detail">${esc(data.answered.detail)}</div>`;
            }

            // Only the sources the answer cites; none for a not-found answer.
            if (data.sources && data.sources.length > 0) {
                html += `<div class="sources-list"><strong>Sources used:</strong>`;
                data.sources.forEach(s => {
                    html += `
                        <div class="source-item">
                            <div class="source-path" title="${escAttr(s.full_path)}">[${esc(s.n)}] ${esc(s.path)}</div>
                            <div class="source-excerpt">${esc(s.excerpt)}</div>
                        </div>
                    `;
                });
                html += `</div>`;
            }
            // The model answered but cited nothing: the top-ranked passage, labelled as not cited.
            if (data.closest) {
                html += `<div class="sources-list"><strong>${esc(data.closest.label)}:</strong>`;
                html += `
                    <div class="source-item">
                        <div class="source-path" title="${escAttr(data.closest.full_path)}">${esc(data.closest.path)}</div>
                        <div class="source-excerpt">${esc(data.closest.excerpt)}</div>
                    </div>
                </div>`;
            }
            results.innerHTML = html;
        }
    </script>
</body>
</html>
"""

_MD_LINE_START = re.compile(r"^\s{0,3}(?:#{1,6}\s+|>\s?|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_EMPHASIS = re.compile(r"\*\*|__|`|~~")
_MD_STAR = re.compile(r"(?<![\w*])\*(\S[^*]*?)\*(?![\w*])")


def _plain(text: Optional[str]) -> str:
    """The passage without Markdown marks: headings, bullets, checkboxes, quotes,
    links (their text stays), bold, italics with *, code ticks and strike-through.
    Headings, list items and paragraphs are joined with " · " so they stay apart."""
    parts = []  # (text, is_break): headings, bullets and blank lines start a new part
    for line in (text or "").splitlines():
        stripped = _MD_LINE_START.sub("", line)
        parts.append((stripped.strip(), stripped != line or not line.strip()))
    flat, prev_break = "", True
    for piece, is_break in parts:
        if not piece:
            prev_break = True
            continue
        sep = "" if not flat else (" · " if (is_break or prev_break) else " ")
        flat += sep + piece
        prev_break = is_break
    flat = _MD_LINK.sub(r"\1", flat)
    flat = _MD_EMPHASIS.sub("", flat)
    return _MD_STAR.sub(r"\1", flat)


def _excerpt(text: Optional[str], width: int = 240) -> str:
    """One line of the passage as plain text, whitespace collapsed, cut at ``width`` characters."""
    flat = " ".join(_plain(text).split())
    return flat if len(flat) <= width else flat[: width - 1].rstrip() + "…"


def _short_path(path: str) -> str:
    """A path short enough to read on screen: relative to the current (memory) folder when
    inside it, else the file and its folder (``demo_dataset/team_sync.md``). A value that
    is not an absolute path (a document hash) is returned unchanged."""
    if not path or not os.path.isabs(path):
        return path
    try:
        rel = os.path.relpath(path)
        if not rel.startswith(".."):
            return rel
    except ValueError:  # another drive on Windows
        pass
    folder = os.path.basename(os.path.dirname(path))
    return os.path.join(folder, os.path.basename(path)) if folder else os.path.basename(path)


def _ollama_hostname(host: Optional[str]) -> str:
    """The machine an Ollama host setting (OLLAMA_HOST) points at; "" when unset."""
    h = (host or "").strip()
    if not h:
        return ""
    if "://" not in h:
        h = "http://" + h
    try:
        return urlsplit(h).hostname or ""
    except ValueError:
        return h


def _on_this_machine(hostname: str) -> bool:
    """True for no host (the Ollama client then uses localhost), localhost, a loopback
    address (127.0.0.0/8, ::1) or the unspecified address (0.0.0.0, ::), which a client
    connects to on this machine."""
    if not hostname or hostname.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified


def answered_line(model: Optional[dict], brand: Optional[str] = None,
                  ollama_host: Optional[str] = None, platform: Optional[str] = None) -> Optional[dict]:
    """The overlay's answer line: ``{"main", "detail", "on_device"}``, or None when no model
    answered (not found).

    It says "answered on this device" and "Nothing left this Mac" only when the answer
    really stayed here: a local provider, and for Ollama a host on this machine.
    ``model_info()`` reports every Ollama as local, so the host is checked here
    (OLLAMA_HOST, as the Ollama client reads it). Anything else is worded as remote.
    """
    if not model:
        return None
    brand = brand if brand is not None else getattr(config, "display_brand", "Smritium")
    platform = platform if platform is not None else sys.platform
    here = "this Mac" if platform == "darwin" else "this computer"
    name, provider = model.get("name", "?"), model.get("provider", "?")
    host = _ollama_hostname(os.environ.get("OLLAMA_HOST") if ollama_host is None else ollama_host)
    if model.get("location") == "local" and (provider != "ollama" or _on_this_machine(host)):
        return {"main": f"{brand} · answered on this device",
                "detail": f"Model: {name}, running locally. Nothing left {here}.",
                "on_device": True}
    if provider == "ollama":
        return {"main": f"{brand} · answered via ollama on {host} (remote)",
                "detail": f"Model: {name}, running on {host}.",
                "on_device": False}
    return {"main": f"{brand} · answered via {provider} (remote)",
            "detail": f"Model: {name}.",
            "on_device": False}


class OverlayAPI:
    """The object pywebview exposes to the page as ``pywebview.api``.

    pywebview walks every public attribute of this object (recursively) and exposes each
    method to the page, so the only public names here are the two methods the page calls:
    ``query`` and ``hide_window``. Everything else (the engine, the model client, the
    window callback) is private, so the page cannot reach engine internals and pywebview
    does not try to walk them at launch.
    """
    def __init__(self, on_hide: Optional[Callable[[], None]] = None):
        self._rehydrator = ContextRehydrator()
        self._llm = LocalLLM()
        self._on_hide = on_hide

    def query(self, text: str) -> dict:
        """Handle query from frontend.

        ``sources`` lists only the passages the answer cites (number, short path, full
        path, one-line plain-text excerpt), and none when the model abstains, matching
        `upii ask` and MCP. ``closest`` is set only when the model answered but cited
        nothing: the top-ranked passage under UNCITED_LABEL, as `upii ask` shows it. ``ranking`` keeps the per-signal ranking of every retrieved
        passage for debugging; the overlay does not display it.
        """
        try:
            # 1. Rehydrate
            ranked_chunks = self._rehydrator.rehydrate(text, limit=5,
                                                       min_similarity=config.rag_min_similarity)
            if not ranked_chunks:
                return {"answer": NOT_FOUND_MESSAGE, "found": False, "model": None,
                        "answered": None, "sources": [], "closest": None, "ranking": []}

            # 2. Generate
            answer = self._llm.answer(text, ranked_chunks)

            # 3. Cited sources only
            sources = []
            if answer.found:
                for n in answer.cited:
                    c = ranked_chunks[n - 1]
                    full = _doc_path(c.doc_hash)
                    sources.append({"n": n, "path": _short_path(full), "full_path": full,
                                    "excerpt": _excerpt(c.text)})

            # 3b. Answered without a citation: never invent one; show the top passage, labelled.
            closest = None
            if answer.found and not answer.cited:
                from upii.cli import UNCITED_LABEL  # one label for both surfaces
                c = ranked_chunks[0]
                full = _doc_path(c.doc_hash)
                closest = {"label": UNCITED_LABEL, "path": _short_path(full), "full_path": full,
                           "excerpt": _excerpt(c.text)}

            model = self._llm.model_info()

            # 4. Per-signal ranking (debug only, not displayed)
            ranking_info = []
            for c in ranked_chunks:
                ranking_info.append({
                    "source": c.source_signal, # vector, calendar, entity
                    "reason": c.boost_reason,
                    "preview": c.text[:50] + "..."
                })

            from upii.cli import display_answer  # same plain text as upii ask
            return {
                "answer": display_answer(answer.text),
                "found": answer.found,
                "model": model,
                "answered": answered_line(model),
                "sources": sources,
                "closest": closest,
                "ranking": ranking_info
            }
        except Exception as e:
            logger.error(f"Overlay Query Error: {e}")
            return {"error": str(e)}

    def hide_window(self):
        """Called by the page on Escape: hide the window (Cmd+Shift+K shows it again)."""
        if self._on_hide is not None:
            self._on_hide()


def _doc_path(doc_hash: str) -> str:
    """The document's path as stored at ingest; the hash if it has none (synthetic)."""
    try:
        from upii.storage.db import DB
        doc = DB().get_document_by_id(doc_hash)
    except Exception:
        doc = None
    return (doc or {}).get("source_path") or doc_hash


class OverlayApp:
    """The overlay window. It owns the shown/hidden state, so Escape (from the page) and
    the Cmd+Shift+K hotkey (from the daemon thread) always agree on it."""

    def __init__(self, debug: bool = False):
        self.debug = debug  # web inspector; off unless `upii overlay --debug`
        self.api = OverlayAPI(on_hide=lambda: self.hide("escape"))
        self.window = None
        self.visible = True  # pywebview shows the window when it starts

    def hide(self, source: str = "escape"):
        if self.window is not None and self.visible:
            self.window.hide()
            self.visible = False
            self._check(source, "hide", expect=False)

    def show(self, source: str = "hotkey"):
        if self.window is not None and not self.visible:
            self.window.show()
            self.window.restore()  # in case it was minimised
            self.visible = True
            self._check(source, "show", expect=True)

    def toggle(self, source: str = "hotkey"):
        if self.visible:
            self.hide(source)
        else:
            self.show(source)

    def native_visible(self) -> Optional[bool]:
        """Whether the OS window is really on screen (macOS: NSWindow.isVisible), or
        None when the backend does not tell us."""
        try:
            native = self.window.native
            return bool(native.isVisible()) if hasattr(native, "isVisible") else None
        except Exception:
            return None

    def _check(self, source: str, action: str, expect: bool, delay: float = CHECK_DELAY):
        """pywebview runs hide/show later on the GUI thread. Shortly after, compare the
        real window with what we asked for: print a warning if they differ (always), and
        a trace line with --debug. This makes a toggle that silently does nothing visible."""
        def run():
            actual = self.native_visible()
            if self.debug:
                print(f"overlay: {source} -> {action}; window visible = {actual}", flush=True)
            if actual is not None and actual != expect:
                print(f"overlay: warning: {source} asked to {action} the window, but it is "
                      f"{'still' if actual else 'not'} visible", flush=True)
        t = threading.Timer(delay, run)
        t.daemon = True
        t.start()

    def launch(self):
        if not webview:
            print("Error: pywebview not installed. Run 'pip install pywebview'")
            return

        self.window = webview.create_window(
            'UPII',
            html=HTML_TEMPLATE,
            js_api=self.api,
            width=800,
            height=600,
            frameless=True,
            transparent=True,
            on_top=True
        )
        webview.start(debug=self.debug)
