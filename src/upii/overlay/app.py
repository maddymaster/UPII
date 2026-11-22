
import logging
import json
import threading
from typing import Optional

try:
    import webview
except ImportError:
    webview = None

from upii.analysis.rehydration import ContextRehydrator
from upii.analysis.llm import NOT_FOUND_MESSAGE, LocalLLM
from upii.core.config import config
from upii.core.types import RankedChunk

logger = logging.getLogger("upii.overlay")

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
            background: rgba(30, 30, 30, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.1);
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
            margin-bottom: 20px;
            line-height: 1.6;
            font-size: 16px;
        }
        
        .sources-list {
            margin-top: 15px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.5);
        }
        
        .source-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .tag-vector { color: #64b5f6; }
        .tag-calendar { color: #ffb74d; }
        .tag-entity { color: #81c784; }

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

        function renderResponse(data) {
            if (data.error) {
                results.innerHTML = `<div style="color:red">${esc(data.error)}</div>`;
                return;
            }

            let html = `<div class="answer-block">${esc(data.answer).replace(/\\n/g, '<br>')}</div>`;
            if (data.model) {
                html += `<div style="opacity:0.6;font-size:12px">Answered by: ${esc(data.model.name)} (${esc(data.model.provider)}, ${esc(data.model.location)})</div>`;
            }

            // Only the sources the answer cites; none for a not-found answer.
            if (data.sources && data.sources.length > 0) {
                html += `<div class="sources-list"><strong>Sources used:</strong>`;
                data.sources.forEach(s => {
                    html += `
                        <div class="source-item">
                            <span>[${esc(s.n)}] ${esc(s.path)}</span>
                            <div style="opacity:0.7;font-size:12px">${esc(s.excerpt)}</div>
                        </div>
                    `;
                });
                html += `</div>`;
            }
            results.innerHTML = html;
        }
    </script>
</body>
</html>
"""

def _excerpt(text: Optional[str], width: int = 240) -> str:
    """One line of the passage, whitespace collapsed, cut at ``width`` characters."""
    flat = " ".join((text or "").split())
    return flat if len(flat) <= width else flat[: width - 1].rstrip() + "…"


class OverlayAPI:
    """Exposed to JS."""
    def __init__(self):
        self.rehydrator = ContextRehydrator()
        self.llm = LocalLLM()
    
    def query(self, text: str) -> dict:
        """Handle query from frontend.

        ``sources`` lists only the passages the answer cites (number, document path,
        one-line excerpt), and none when the model abstains, matching `upii ask` and MCP.
        ``ranking`` keeps the per-signal ranking of every retrieved passage for debugging;
        the overlay does not display it.
        """
        try:
            # 1. Rehydrate
            ranked_chunks = self.rehydrator.rehydrate(text, limit=5,
                                                      min_similarity=config.rag_min_similarity)
            if not ranked_chunks:
                return {"answer": NOT_FOUND_MESSAGE, "found": False, "model": None,
                        "sources": [], "ranking": []}

            # 2. Generate
            answer = self.llm.answer(text, ranked_chunks)

            # 3. Cited sources only
            sources = []
            if answer.found:
                for n in answer.cited:
                    c = ranked_chunks[n - 1]
                    sources.append({"n": n, "path": self._doc_path(c.doc_hash),
                                    "excerpt": _excerpt(c.text)})

            # 4. Per-signal ranking (debug only, not displayed)
            ranking_info = []
            for c in ranked_chunks:
                ranking_info.append({
                    "source": c.source_signal, # vector, calendar, entity
                    "reason": c.boost_reason,
                    "preview": c.text[:50] + "..."
                })

            return {
                "answer": answer.text,
                "found": answer.found,
                "model": self.llm.model_info(),
                "sources": sources,
                "ranking": ranking_info
            }
        except Exception as e:
            logger.error(f"Overlay Query Error: {e}")
            return {"error": str(e)}

    def _doc_path(self, doc_hash: str) -> str:
        """The document's path as stored at ingest; the hash if it has none (synthetic)."""
        try:
            from upii.storage.db import DB
            doc = DB().get_document_by_id(doc_hash)
        except Exception:
            doc = None
        return (doc or {}).get("source_path") or doc_hash

    def hide_window(self):
        """Allow JS to close/hide window."""
        # This relies on the main thread loop to handle actual window ops usually
        # But we can try calling exit or hide if supported
        # For pynput daemon integration, we usually just minimize
        pass

class OverlayApp:
    def __init__(self):
        self.api = OverlayAPI()
        self.window = None

    def launch(self):
        if not webview:
            print("Error: pywebview not installed. Run 'pip install pywebview'")
            return

        # Create invisible window initially? pywebview typically shows immediately.
        # We start it, then the daemon monitors hotkeys to show/hide.
        # For "Instant" feel, we want it running.
        
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
        webview.start(debug=True)
