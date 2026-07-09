"""Smoke tests for `upii knowledge --graph` HTML rendering.

Seeds a small entity graph, renders it, and asserts the output is a
self-contained, well-formed HTML document with no external/cloud calls.
"""
import re
from html.parser import HTMLParser

import pytest

from upii.core.config import config
from upii.storage.db import DB


class _WellFormednessChecker(HTMLParser):
    """Minimal structural check: tags nest and balance (ignoring void/self-closing)."""

    VOID = {"meta", "br", "img", "input", "hr", "link", "canvas"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.ok = True

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        # Pop to the matching open tag if present.
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass
        else:
            self.ok = False


@pytest.fixture
def seeded_db(tmp_path):
    """A DB with 3 entities and edges that make two of them co-occur in a chunk."""
    config.db_path = str(tmp_path / "graph_test.db")
    db = DB()
    db.init_db()

    omega = db.add_entity("Project Omega", "PROJECT")
    alice = db.add_entity("Alice", "PERSON")
    nasa = db.add_entity("NASA", "ORGANIZATION")

    # Omega + Alice share chunk c1 (co-occur, weight 1 from this chunk),
    # and also share c2 -> weight 2 total. NASA only appears in c3 (isolated).
    db.add_entity_edge(omega, "c1", "doc1", "omega ctx 1")
    db.add_entity_edge(alice, "c1", "doc1", "alice ctx 1")
    db.add_entity_edge(omega, "c2", "doc1", "omega ctx 2")
    db.add_entity_edge(alice, "c2", "doc1", "alice ctx 2")
    db.add_entity_edge(nasa, "c3", "doc2", "nasa ctx")
    return db


def test_graph_data_shape(seeded_db):
    from upii.analysis.graph import build_graph_data

    data = build_graph_data(seeded_db)
    assert len(data["nodes"]) == 3
    names = {n["name"] for n in data["nodes"]}
    assert names == {"Project Omega", "Alice", "NASA"}

    # Exactly one co-occurrence edge (Omega<->Alice) with weight 2 (chunks c1,c2).
    assert len(data["links"]) == 1
    edge = data["links"][0]
    assert edge["weight"] == 2

    # Categories are each mapped to a distinct colour in the legend.
    assert len(data["legend"]) == 3
    colours = {item["colour"] for item in data["legend"]}
    assert len(colours) == 3


def test_render_produces_valid_selfcontained_html(seeded_db):
    from upii.analysis.graph import render_html, build_graph_data

    doc = render_html(build_graph_data(seeded_db))

    # Looks like an HTML document.
    assert doc.lstrip().lower().startswith("<!doctype html>")
    assert "<html" in doc and "</html>" in doc
    assert "<canvas" in doc

    # Well-formed / balanced tags.
    checker = _WellFormednessChecker()
    checker.feed(doc)
    assert checker.ok, "unbalanced HTML tags"
    assert not checker.stack, f"unclosed tags: {checker.stack}"

    # Entity names made it into the payload.
    assert "Project Omega" in doc
    assert "NASA" in doc

    # Self-contained: no external/cloud references of any kind.
    assert not re.search(r"https?://", doc), "output must not reference external URLs"
    assert "src=" not in doc, "no external script/resource references allowed"


def test_write_graph_command(tmp_path, seeded_db):
    """End-to-end: the CLI `knowledge --graph --out` path writes a real file."""
    from typer.testing import CliRunner
    from upii.cli import app

    out = tmp_path / "graph.html"
    runner = CliRunner()
    result = runner.invoke(app, ["knowledge", "--graph", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert content.lstrip().lower().startswith("<!doctype html>")
    assert "Project Omega" in content


def test_empty_graph_still_valid(tmp_path):
    """An empty DB renders a valid HTML file rather than crashing."""
    config.db_path = str(tmp_path / "empty.db")
    db = DB()
    db.init_db()

    from upii.analysis.graph import render_html, build_graph_data

    doc = render_html(build_graph_data(db))
    assert doc.lstrip().lower().startswith("<!doctype html>")
    assert "0 entities" in doc
    checker = _WellFormednessChecker()
    checker.feed(doc)
    assert checker.ok and not checker.stack
