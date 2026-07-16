#!/usr/bin/env python3
"""Deterministic labelled corpus for entity-extraction evaluation.

Produces ``corpus/doc_XXX.md`` and ``gold.json`` as a pure function of ``--seed``,
so the fixture is byte-reproducible on any machine. Gold labels are defined *by
construction*: whenever the generator fills an entity slot it records the
(canonical name, type); distractors are never recorded. Difficulty is real, not
synthetic-easy — the same message can be honestly hard to extract from:

- **Realistic surface forms** the fixture deliberately includes: acronym orgs
  (``NASA``, ``ICEYE``), single-token people (``Priya``), titled people
  (``Dr. Sivan``), corporate-suffix orgs (``Acme Corp``), project triggers
  (``Project Omega``).
- **Adversarial distractors** that create false-positive pressure and never
  appear in gold: sentence-initial capitals, month/day names, section headers,
  all-caps tech acronyms (``SLO``, ``API``, ``KPI``), and multi-word capitalised
  non-entities (``Machine Learning``, ``New York``, ``Vector Store``).

Entities are placed in *varied* sentence positions chosen independently of any
extractor's rules — some catchable, some not — so recall measured against this
set is honest rather than tuned.

Usage
-----
    python eval/entities/generate_corpus.py                 # 500 docs, seed 1729
    python eval/entities/generate_corpus.py --docs 50 --seed 7
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
GOLD_PATH = HERE / "gold.json"

# --- entity inventories (canonical name, as it should be extracted) -----------

PEOPLE_SINGLE = ["Priya", "Sarah", "Raj", "Veena", "Omar", "Lena", "Diego",
                 "Fatima", "Chen", "Marcus", "Aisha", "Tomas"]
PEOPLE_FULL = ["Alice Smith", "John Carter", "Maria Gonzalez", "David Okafor",
               "Nina Patel", "Erik Lindqvist", "Grace Mensah"]
PEOPLE_TITLED = ["Dr. Sivan", "Prof. Lin", "Ms. Osei", "Mr. Tanaka",
                 "Dr. Ramachandran", "Prof. Alvarez"]

# Realistic but uncommon names, deliberately absent from any typical
# common-given-names gazetteer. A rule-based extractor with no title cue cannot
# recover these, so they hold recall honestly below 1.0 rather than letting the
# gazetteer and this fixture silently agree. (Titled variants ARE recoverable via
# the title cue, which is the point — the title, not the name, carries the signal.)
PEOPLE_UNCOMMON_BARE = ["Oyelaran", "Nakamura", "Bergström", "Adeyemi",
                        "Kowalski", "Okonkwo", "Thirunavukarasu"]

ORGS_ACRONYM = ["NASA", "ICEYE", "ISRO", "ESA", "NOAA", "DARPA", "CNES"]
ORGS_SUFFIX = ["Acme Corp", "Globex Inc", "Initech LLC", "Umbrella Ltd",
               "Vertex Labs", "Meridian Systems", "Cascade Technologies",
               "Halcyon Foundation", "Borealis Institute", "Skyline Agency"]

PROJECTS = ["Project Omega", "Project Atlas", "Project Nimbus", "Project Meridian",
            "Operation Borealis", "Operation Cascade", "Codename Vertex",
            "Project Halcyon"]

# --- distractors: capitalised things that must NOT be extracted ---------------

DISTRACTOR_ACRONYMS = ["SLO", "API", "KPI", "CPU", "GPU", "RAM", "JSON", "CI",
                       "QA", "ML", "RAG", "LLM", "MRR", "SDK", "SQL"]
DISTRACTOR_MULTIWORD = ["Machine Learning", "New York", "Vector Store",
                        "Context Window", "Data Pipeline", "Design Review",
                        "Release Candidate", "North Star", "Deep Learning"]
DISTRACTOR_HEADERS = ["Overview", "Summary", "Background", "Next Steps",
                      "Action Items", "Roadmap", "Notes", "Decisions"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MONTHS = ["January", "March", "April", "June", "September", "November"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
SENTENCE_STARTERS = ["We", "The team", "This", "After the review", "Meanwhile",
                     "During standup", "Later", "Overall"]

TOPICS = ["the latency budget", "the migration plan", "the pricing model",
          "the incident postmortem", "the hiring loop", "the data schema",
          "the rollout timeline", "the eval harness"]


def _person():
    """Return (surface, canonical, 'PERSON'). Canonical == surface here.

    ~15% of people are drawn from the uncommon-name pool so recall reflects the
    gazetteer's real coverage, not a fixture tuned to it.
    """
    if random.random() < 0.15:
        name = random.choice(PEOPLE_UNCOMMON_BARE)
    else:
        name = random.choice(PEOPLE_SINGLE + PEOPLE_FULL + PEOPLE_TITLED)
    return name, name, "PERSON"


def _org():
    name = random.choice(ORGS_ACRONYM + ORGS_SUFFIX)
    return name, name, "ORG"


def _project():
    name = random.choice(PROJECTS)
    return name, name, "PROJECT"


# Sentence templates. Each returns (text, [gold entities]). Entity-bearing
# templates place the entity in a variety of positions on purpose; distractor
# templates place look-alike capitalised spans and yield no gold.

def _t_met(g):
    s, c, t = _person()
    return f"Met with {s} to walk through {random.choice(TOPICS)}.", [(c, t)]

def _t_person_initial(g):
    s, c, t = _person()
    return f"{s} raised a concern about {random.choice(TOPICS)}.", [(c, t)]

def _t_two_people(g):
    (s1, c1, t1), (s2, c2, t2) = _person(), _person()
    return f"{s1} and {s2} will pair on {random.choice(TOPICS)}.", [(c1, t1), (c2, t2)]

def _t_org_confirm(g):
    s, c, t = _org()
    return f"{s} confirmed the integration timeline for next {random.choice(QUARTERS)}.", [(c, t)]

def _t_org_prep(g):
    s, c, t = _org()
    return f"According to {s}, the {random.choice(DISTRACTOR_MULTIWORD)} approach is preferred.", [(c, t)]

def _t_project_kickoff(g):
    s, c, t = _project()
    return f"We kicked off {s} last {random.choice(DAYS)}.", [(c, t)]

def _t_project_status(g):
    s, c, t = _project()
    return f"{s} is on track for {random.choice(MONTHS)}.", [(c, t)]

def _t_person_org(g):
    (ps, pc, pt), (os_, oc, ot) = _person(), _org()
    return f"{ps} synced with {os_} on {random.choice(TOPICS)}.", [(pc, pt), (oc, ot)]

def _t_person_project(g):
    (ps, pc, pt), (prs, prc, prt) = _person(), _project()
    return f"{ps} is now leading {prs}.", [(pc, pt), (prc, prt)]

# distractor-only templates (no gold)
def _d_acronym(g):
    return f"{random.choice(DISTRACTOR_ACRONYMS)} latency exceeded the {random.choice(DISTRACTOR_ACRONYMS)} target on {random.choice(DAYS)}.", []

def _d_multiword(g):
    return f"The {random.choice(DISTRACTOR_MULTIWORD)} work stalled while {random.choice(SENTENCE_STARTERS)} regrouped.", []

def _d_starter(g):
    return f"{random.choice(SENTENCE_STARTERS)} reviewed {random.choice(TOPICS)} on {random.choice(DAYS)}.", []

def _d_place(g):
    return f"The offsite in {random.choice(DISTRACTOR_MULTIWORD)} covered {random.choice(TOPICS)}.", []


ENTITY_TEMPLATES = [_t_met, _t_person_initial, _t_two_people, _t_org_confirm,
                    _t_org_prep, _t_project_kickoff, _t_project_status,
                    _t_person_org, _t_person_project]
DISTRACTOR_TEMPLATES = [_d_acronym, _d_multiword, _d_starter, _d_place]


def _make_doc(idx: int):
    """Build one markdown doc + its gold entity set (deduped)."""
    header = random.choice(DISTRACTOR_HEADERS)
    lines = [f"# {header} — note {idx:03d}", ""]
    gold = set()
    n_sent = random.randint(5, 11)
    for _ in range(n_sent):
        # ~65% entity-bearing, ~35% pure distractor — realistic density.
        if random.random() < 0.65:
            text, ents = random.choice(ENTITY_TEMPLATES)(None)
            for name, typ in ents:
                gold.add((name, typ))
        else:
            text, _ = random.choice(DISTRACTOR_TEMPLATES)(None)
        lines.append(text)
    return "\n".join(lines) + "\n", sorted(gold)


def _fingerprint(files) -> str:
    h = hashlib.sha256()
    for name in sorted(f.name for f in files):
        h.update(name.encode())
        h.update(b"\0")
        h.update((CORPUS_DIR / name).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1729)
    args = ap.parse_args()

    random.seed(args.seed)
    if CORPUS_DIR.exists():
        for f in CORPUS_DIR.glob("*.md"):
            f.unlink()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    docs_gold = {}
    n_entities = 0
    for i in range(args.docs):
        text, gold = _make_doc(i)
        fname = f"doc_{i:03d}.md"
        (CORPUS_DIR / fname).write_text(text, encoding="utf-8")
        docs_gold[fname] = [[name, typ] for name, typ in gold]
        n_entities += len(gold)

    fp = _fingerprint(list(CORPUS_DIR.glob("*.md")))
    payload = {
        "seed": args.seed,
        "n_docs": args.docs,
        "n_gold_entities": n_entities,
        "corpus_fingerprint": fp,
        "types": ["PERSON", "ORG", "PROJECT"],
        "docs": docs_gold,
    }
    with GOLD_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    by_type = {}
    for ents in docs_gold.values():
        for _, t in ents:
            by_type[t] = by_type.get(t, 0) + 1
    print(f"generated {args.docs} docs, {n_entities} gold entities (seed {args.seed})")
    print(f"  by type: {by_type}")
    print(f"  fingerprint: {fp[:16]}…  ->  {GOLD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
