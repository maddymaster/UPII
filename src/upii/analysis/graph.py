"""Local knowledge-graph visualisation.

Renders the `entities` + `entity_edges` tables from `upii.db` as a single
self-contained interactive HTML file. There are **no external or cloud calls**:
the force-directed layout is a small vendored vanilla-JS simulation embedded
inline, so the output opens offline with nothing but a browser.

Nodes are coloured by entity category; edges are weighted (line thickness) by
how many chunks the two entities co-occur in.
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Optional

from upii.storage.db import DB

# A fixed, colour-blind-friendly palette. Categories beyond this list wrap
# around; keeping it deterministic means the same category is always the same
# colour across renders.
_PALETTE = [
    "#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
    "#76b7b2", "#edc948", "#ff9da7", "#9c755f", "#bab0ac",
]


def _category_colours(categories: List[str]) -> Dict[str, str]:
    """Assign a stable colour to each distinct category (sorted for determinism)."""
    return {cat: _PALETTE[i % len(_PALETTE)] for i, cat in enumerate(sorted(categories))}


def build_graph_data(db: Optional[DB] = None) -> Dict[str, Any]:
    """Collect nodes + edges + the category colour legend from the local DB."""
    db = db or DB()
    # Drop orphan nodes (degree 0) — e.g. entities whose only document was later
    # removed. They carry no edges, so they add nothing but clutter to the layout.
    entities = [e for e in db.get_entities() if e["degree"] > 0]
    edges = db.get_cooccurrence_edges()

    categories = sorted({e["category"] for e in entities})
    colours = _category_colours(categories)

    nodes = [
        {
            "id": e["entity_id"],
            "name": e["name"],
            "category": e["category"],
            "degree": e["degree"],
            "colour": colours[e["category"]],
        }
        for e in entities
    ]
    links = [
        {"source": e["source"], "target": e["target"], "weight": e["weight"]}
        for e in edges
    ]
    legend = [{"category": cat, "colour": colours[cat]} for cat in categories]
    return {"nodes": nodes, "links": links, "legend": legend}


def render_html(data: Dict[str, Any], title: str = "UPII Knowledge Graph") -> str:
    """Produce a fully self-contained HTML document for the graph data.

    The layout engine (`_GRAPH_JS`) is vendored inline — no CDN, no fonts, no
    network. The graph data is injected as a JSON blob the script reads on load.
    """
    payload = json.dumps(data, separators=(",", ":"))
    safe_title = html.escape(title)
    node_count = len(data["nodes"])
    link_count = len(data["links"])
    return _HTML_TEMPLATE.format(
        title=safe_title,
        payload=payload,
        node_count=node_count,
        link_count=link_count,
        graph_js=_GRAPH_JS,
    )


def write_graph(out_path: str, db: Optional[DB] = None, title: str = "UPII Knowledge Graph") -> Dict[str, Any]:
    """Build the graph from the DB and write the HTML file. Returns the graph data."""
    data = build_graph_data(db)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_html(data, title=title))
    return data


# --- Vendored force-directed layout (dependency-free) ----------------------
# A compact velocity-Verlet force simulation: repulsion between all nodes,
# spring attraction along edges, and a mild centring pull. Rendered on a 2D
# canvas with drag + zoom/pan. Kept intentionally small so the whole thing is
# readable and truly self-contained.
_GRAPH_JS = r"""
const DATA = window.__UPII_GRAPH__;
const canvas = document.getElementById('graph');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');

let W = 0, H = 0, DPR = window.devicePixelRatio || 1;
function resize() {
  W = canvas.clientWidth; H = canvas.clientHeight;
  canvas.width = W * DPR; canvas.height = H * DPR;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
}
window.addEventListener('resize', () => { resize(); });

// Build node/link structures with initial positions on a circle (deterministic).
const nodes = DATA.nodes.map((n, i) => {
  const a = (i / Math.max(1, DATA.nodes.length)) * Math.PI * 2;
  return Object.assign({}, n, {
    x: Math.cos(a) * 120, y: Math.sin(a) * 120, vx: 0, vy: 0,
  });
});
const byId = new Map(nodes.map(n => [n.id, n]));
const links = DATA.links
  .map(l => ({ source: byId.get(l.source), target: byId.get(l.target), weight: l.weight }))
  .filter(l => l.source && l.target);

const maxWeight = links.reduce((m, l) => Math.max(m, l.weight), 1);
const maxDegree = nodes.reduce((m, n) => Math.max(m, n.degree), 1);
function radius(n) { return 5 + 9 * Math.sqrt(n.degree / maxDegree); }

// View transform (pan/zoom).
let scale = 1, ox = 0, oy = 0;
function toScreen(x, y) { return [x * scale + W / 2 + ox, y * scale + H / 2 + oy]; }
function toWorld(sx, sy) { return [(sx - W / 2 - ox) / scale, (sy - H / 2 - oy) / scale]; }

// Force simulation (a few hundred ticks, then idle-redraw on interaction).
let alpha = 1.0;
function tick() {
  const REPULSION = 4000, SPRING = 0.02, SPRING_LEN = 70, CENTER = 0.01;
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let d2 = dx * dx + dy * dy || 0.01;
      const f = REPULSION / d2;
      const d = Math.sqrt(d2);
      const fx = (dx / d) * f, fy = (dy / d) * f;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    }
  }
  for (const l of links) {
    let dx = l.target.x - l.source.x, dy = l.target.y - l.source.y;
    const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
    const f = SPRING * (d - SPRING_LEN) * (0.5 + l.weight / maxWeight);
    const fx = (dx / d) * f, fy = (dy / d) * f;
    l.source.vx += fx; l.source.vy += fy;
    l.target.vx -= fx; l.target.vy -= fy;
  }
  for (const n of nodes) {
    n.vx -= n.x * CENTER; n.vy -= n.y * CENTER;
    if (n === dragging) continue;
    n.x += n.vx * alpha; n.y += n.vy * alpha;
    n.vx *= 0.85; n.vy *= 0.85;
  }
  alpha *= 0.995;
}

function draw() {
  ctx.clearRect(0, 0, W, H);
  // Edges.
  for (const l of links) {
    const [x1, y1] = toScreen(l.source.x, l.source.y);
    const [x2, y2] = toScreen(l.target.x, l.target.y);
    ctx.beginPath();
    ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
    ctx.lineWidth = (0.5 + 3 * (l.weight / maxWeight)) ;
    ctx.strokeStyle = 'rgba(130,130,130,0.45)';
    ctx.stroke();
  }
  // Nodes.
  for (const n of nodes) {
    const [x, y] = toScreen(n.x, n.y);
    const r = radius(n) * Math.sqrt(scale);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = n.colour;
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = 'rgba(255,255,255,0.7)';
    ctx.stroke();
    if (scale > 0.7 || n.degree >= maxDegree * 0.5) {
      ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--fg');
      ctx.font = '12px system-ui, sans-serif';
      ctx.fillText(n.name, x + r + 3, y + 4);
    }
  }
}

function frame() {
  if (alpha > 0.02) { tick(); }
  draw();
  requestAnimationFrame(frame);
}

// --- Interaction: drag nodes, pan, zoom, hover tooltip ---------------------
let dragging = null, panning = false, lastX = 0, lastY = 0;
function pick(sx, sy) {
  const [wx, wy] = toWorld(sx, sy);
  for (const n of nodes) {
    const dx = n.x - wx, dy = n.y - wy;
    if (dx * dx + dy * dy <= Math.pow(radius(n) + 3, 2)) return n;
  }
  return null;
}
canvas.addEventListener('mousedown', e => {
  const n = pick(e.offsetX, e.offsetY);
  if (n) { dragging = n; alpha = Math.max(alpha, 0.3); }
  else { panning = true; }
  lastX = e.offsetX; lastY = e.offsetY;
});
window.addEventListener('mousemove', e => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  if (dragging) {
    const [wx, wy] = toWorld(sx, sy);
    dragging.x = wx; dragging.y = wy; dragging.vx = 0; dragging.vy = 0;
  } else if (panning) {
    ox += sx - lastX; oy += sy - lastY; lastX = sx; lastY = sy;
  } else {
    const n = pick(sx, sy);
    if (n) {
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX + 12) + 'px';
      tooltip.style.top = (e.clientY + 12) + 'px';
      tooltip.innerHTML = '<b>' + n.name + '</b><br>' + n.category + ' · ' + n.degree + ' link(s)';
    } else { tooltip.style.display = 'none'; }
  }
});
window.addEventListener('mouseup', () => { dragging = null; panning = false; });
canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 0.9;
  const [wx, wy] = toWorld(e.offsetX, e.offsetY);
  scale *= factor;
  const [nx, ny] = toScreen(wx, wy);
  ox += e.offsetX - nx; oy += e.offsetY - ny;
}, { passive: false });

resize();
frame();
"""

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg: #ffffff; --fg: #1a1a1a; --panel: rgba(0,0,0,0.04); }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #14161a; --fg: #e6e6e6; --panel: rgba(255,255,255,0.06); }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; background: var(--bg); color: var(--fg);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }}
  header {{ padding: 12px 16px; border-bottom: 1px solid var(--panel); }}
  header h1 {{ margin: 0; font-size: 16px; font-weight: 600; }}
  header .meta {{ font-size: 12px; opacity: 0.65; margin-top: 2px; }}
  #graph {{ display: block; width: 100vw; height: calc(100vh - 58px); cursor: grab; }}
  #graph:active {{ cursor: grabbing; }}
  #legend {{ position: fixed; top: 70px; left: 16px; background: var(--panel);
    padding: 10px 12px; border-radius: 8px; font-size: 12px; max-width: 220px;
    backdrop-filter: blur(4px); }}
  #legend .row {{ display: flex; align-items: center; gap: 8px; margin: 3px 0; }}
  #legend .dot {{ width: 11px; height: 11px; border-radius: 50%; flex: 0 0 auto; }}
  #tooltip {{ position: fixed; display: none; pointer-events: none; z-index: 10;
    background: var(--bg); color: var(--fg); border: 1px solid var(--panel);
    padding: 6px 9px; border-radius: 6px; font-size: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25); }}
  #empty {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%);
    opacity: 0.5; font-size: 14px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">{node_count} entities · {link_count} co-occurrence edges · drag to move · scroll to zoom</div>
</header>
<canvas id="graph"></canvas>
<div id="legend"></div>
<div id="tooltip"></div>
<script>
window.__UPII_GRAPH__ = {payload};
(function() {{
  const legend = document.getElementById('legend');
  const L = window.__UPII_GRAPH__.legend || [];
  if (!L.length) legend.style.display = 'none';
  for (const item of L) {{
    const row = document.createElement('div'); row.className = 'row';
    const dot = document.createElement('span'); dot.className = 'dot';
    dot.style.background = item.colour;
    const label = document.createElement('span'); label.textContent = item.category;
    row.appendChild(dot); row.appendChild(label); legend.appendChild(row);
  }}
  if (!window.__UPII_GRAPH__.nodes.length) {{
    const e = document.createElement('div'); e.id = 'empty';
    e.textContent = 'Knowledge graph is empty — ingest documents to populate entities.';
    document.body.appendChild(e);
    return;
  }}
{graph_js}
}})();
</script>
</body>
</html>
"""
