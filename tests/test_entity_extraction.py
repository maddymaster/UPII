"""Regression tests for the typed entity extractor (PERSON / ORG / PROJECT).

One or more cases per rule the extractor implements, plus the two bugs found while
building the entity eval (eval/run_entity_eval.py): the org-suffix pattern
swallowing a preceding sentence's word across a full stop, and a repeated entity
leaving its span unclaimed so a bare-name rule re-emitted it.
"""

import pytest

from upii.analysis.entity_extractor import EntityExtractor
from upii.storage.db import DB
from upii.analysis.search import SearchEngine


@pytest.fixture
def ex():
    return EntityExtractor()


def _typed(entities):
    return {(e.name, e.category) for e in entities}


# --- PROJECT: trigger + full surface -----------------------------------------

def test_project_keeps_full_surface(ex):
    # Regression: the old extractor returned group(2) ("Omega"); we keep the full
    # "Project Omega" so extracted names match how projects appear in documents.
    assert ("Project Omega", "PROJECT") in _typed(ex.extract("We kicked off Project Omega."))


@pytest.mark.parametrize("text,name", [
    ("Operation Borealis is on track.", "Operation Borealis"),
    ("Codename Vertex ships in March.", "Codename Vertex"),
])
def test_project_triggers(ex, text, name):
    assert (name, "PROJECT") in _typed(ex.extract(text))


# --- PERSON: title cue -------------------------------------------------------

@pytest.mark.parametrize("text,name", [
    ("Dr. Sivan reviewed the plan.", "Dr. Sivan"),
    ("We spoke to Prof. Lin about it.", "Prof. Lin"),
    ("Ms. Osei signed off.", "Ms. Osei"),
])
def test_person_titled(ex, text, name):
    assert (name, "PERSON") in _typed(ex.extract(text))


# --- PERSON: known given name (single + full) --------------------------------

def test_person_single_known_name(ex):
    assert ("Priya", "PERSON") in _typed(ex.extract("Met with Priya on Tuesday."))


def test_person_full_name_extends_to_surname(ex):
    assert ("Grace Mensah", "PERSON") in _typed(ex.extract("Grace Mensah led the review."))


def test_person_unknown_bare_name_is_missed_not_guessed(ex):
    # Precision-first: an unknown capitalised token with no title cue is NOT a
    # person. This is an accepted recall gap, not a correctness bug.
    assert not any(e.category == "PERSON" for e in ex.extract("Okonkwo joined the call."))


# --- ORG: corporate suffix ---------------------------------------------------

@pytest.mark.parametrize("text,name", [
    ("Acme Corp confirmed the deal.", "Acme Corp"),
    ("Meridian Systems shipped it.", "Meridian Systems"),
    ("Borealis Institute published the paper.", "Borealis Institute"),
])
def test_org_suffix(ex, text, name):
    assert (name, "ORG") in _typed(ex.extract(text))


def test_org_suffix_requires_a_name_in_front(ex):
    # A bare suffix on its own is not an organisation.
    assert not any(e.category == "ORG" for e in ex.extract("The LLC was dissolved."))


# --- ORG: acronym, with tech-acronym stop-list -------------------------------

def test_org_acronym(ex):
    assert ("NASA", "ORG") in _typed(ex.extract("We partnered with NASA."))


@pytest.mark.parametrize("acronym", ["API", "SLO", "GPU", "JSON", "LLM"])
def test_tech_acronyms_are_not_orgs(ex, acronym):
    assert not any(e.category == "ORG" for e in ex.extract(f"The {acronym} target slipped."))


# --- Distractor rejection (precision pressure) -------------------------------

@pytest.mark.parametrize("text", [
    "The Machine Learning work stalled.",     # multi-word capitalised non-entity
    "The offsite in New York went well.",      # place, not person/org
    "Meanwhile reviewed the roadmap.",         # sentence-initial capital
])
def test_capitalised_distractors_are_not_entities(ex, text):
    assert ex.extract(text) == []


# --- Bug regressions ---------------------------------------------------------

def test_org_suffix_does_not_swallow_across_full_stop(ex):
    # Bug: "[...] last Friday. Meridian Systems" matched "Friday. Meridian Systems".
    ents = _typed(ex.extract("We shipped last Friday. Meridian Systems confirmed it."))
    assert ("Meridian Systems", "ORG") in ents
    assert not any("Friday" in name for name, _ in ents)


def test_repeated_entity_claims_span_no_bare_name_leak(ex):
    # Bug: a second "Prof. Lin" hit the dedup return before claiming its span, so
    # the bare-name rule re-emitted "Lin" as a separate PERSON.
    ents = ex.extract("Prof. Lin and Prof. Lin will pair on the postmortem.")
    names = [e.name for e in ents if e.category == "PERSON"]
    assert names == ["Prof. Lin"]  # exactly one, and not a bare "Lin"


# --- Storage + relational integration (unchanged contract) -------------------

def test_db_entity_storage(tmp_path):
    from upii.core.config import config
    config.db_path = str(tmp_path / "upii_test.db")
    db = DB()
    db.init_db()

    eid = db.add_entity("Project Zero", "PROJECT")
    assert eid is not None
    assert db.add_entity("Project Zero", "PROJECT") == eid  # idempotent

    db.add_entity_edge(eid, "hash123", "doc1", "Context about Zero")
    edges = db.get_entity_edges("Project Zero")
    assert len(edges) == 1
    assert edges[0]["chunk_hash"] == "hash123"


def test_search_integration(monkeypatch, tmp_path):
    from upii.core.config import config
    config.db_path = str(tmp_path / "upii_test.db")
    config.vector_store_path = str(tmp_path / "vectors")

    class MockEmbedder:
        def encode(self, text):
            import numpy as np
            return np.zeros(384)

    monkeypatch.setattr("upii.analysis.embeddings.Embedder.get_instance", lambda: MockEmbedder())

    db = DB()
    db.init_db()
    # Stored under the full project name; the extractor now yields the full
    # "Project Secret" from the query too, so the relational lookup matches.
    eid = db.add_entity("Project Secret", "PROJECT")
    db.add_entity_edge(eid, "h_secret", "doc_secret", "The secret project launch is delayed.")

    engine = SearchEngine()
    engine.embedder = MockEmbedder()
    results = engine.search("What is the status of Project Secret?")

    assert any(c.category == "entity_recall" and "Secret" in c.text for c in results), \
        "Entity chunk should have been injected into search results"
