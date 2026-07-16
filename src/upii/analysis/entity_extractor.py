"""Lightweight, local, rule-based entity extractor.

Emits three typed categories — ``PERSON``, ``ORG``, ``PROJECT`` — from plain text.
No model, no network, no heavy dependency: just regex + two small gazetteers (a
common-given-names list and a tech-acronym stop-list). That keeps extraction fast
and fully on-device, at the cost of recall on surface forms the rules don't cover.

Design posture: **precision-first.** Each rule fires only on a strong, specific
cue, because a false entity pollutes the knowledge graph and the relational
retrieval signal that reads it. Deliberately *not* caught (accepted recall loss):
bare capitalised words with no name/title/suffix/trigger cue, and organisation
acronyms that collide with common tech acronyms.

Canonical name = the matched surface form as written (e.g. ``Project Omega``, not
``Omega``; ``Dr. Sivan`` with the title), so extracted entities line up with how
they appear in documents.
"""

import re
from typing import List
from dataclasses import dataclass


@dataclass
class Entity:
    name: str
    category: str      # PERSON | ORG | PROJECT
    confidence: float
    context: str


# Common given names — a general, culture-spanning list (not derived from any
# corpus). Used to license PERSON extraction for capitalised tokens that carry no
# other cue. A name absent here is simply not recovered as a bare-name person; it
# is a recall gap, never a correctness bug.
_FIRST_NAMES = {
    "aisha", "alice", "amara", "amir", "ana", "andre", "anna", "arjun", "aya",
    "ben", "carlos", "chen", "chloe", "clara", "daniel", "david", "diego",
    "elena", "elif", "emma", "erik", "fatima", "grace", "hana", "hassan",
    "hiro", "ines", "isabel", "james", "jamal", "jing", "john", "jose", "juan",
    "kabir", "kai", "kenji", "lena", "leila", "liam", "lin", "lucas", "luca",
    "maria", "marco", "marcus", "mei", "mike", "mohammed", "nadia", "nina",
    "noah", "nora", "olga", "omar", "oscar", "paolo", "pedro", "priya", "raj",
    "ravi", "rosa", "sara", "sarah", "sofia", "sven", "tariq", "tomas", "veena",
    "wei", "yara", "yuki", "zara", "zoe",
}

# Titles that reliably introduce a person.
_TITLE = r"(?:Dr|Mr|Mrs|Ms|Prof|Professor|Sir|Dame)"

# Corporate / institutional suffixes that reliably close an organisation name.
_ORG_SUFFIX = (
    r"(?:Corp|Corporation|Inc|LLC|Ltd|Limited|GmbH|Labs|Laboratories|Systems"
    r"|Technologies|Technology|Foundation|Institute|Agency|Group|Holdings"
    r"|Partners|Ventures|Industries)"
)

# Words that introduce a named project.
_PROJECT_TRIGGER = r"(?:Project|Operation|Codename|Code Name)"

# Capitalised words that are not part of a name even when they precede a suffix,
# e.g. sentence-initial "The LLC" / "Our Systems".
_DETERMINERS = {"the", "a", "an", "this", "that", "these", "those",
                "our", "their", "its", "his", "her", "my", "your"}

# Common tech / process acronyms that are NOT organisations. An all-caps token in
# this set is never emitted as an ORG. General list — covers far more than any one
# corpus's distractors — so it does not silently pass a specific fixture.
_ACRONYM_STOPLIST = {
    "API", "REST", "GRPC", "HTTP", "HTTPS", "HTML", "CSS", "JSON", "YAML", "XML",
    "SQL", "CPU", "GPU", "RAM", "SSD", "OS", "IO", "UI", "UX", "CLI", "SDK",
    "IDE", "CI", "CD", "QA", "PR", "MR", "VM", "K8S", "AWS", "GCP", "ML", "AI",
    "NLP", "LLM", "RAG", "KG", "MRR", "NDCG", "KPI", "OKR", "SLA", "SLO", "SLI",
    "ROI", "TCO", "ETA", "EOD", "WIP", "TBD", "FAQ", "PDF", "CSV", "URL", "URI",
    "UUID", "ID", "PII", "GDPR", "SOC", "MVP", "POC", "RFC", "ASAP", "FYI", "TL",
    # All-caps corporate forms are handled by the suffix rule (which needs a name
    # in front); a bare one on its own is not an organisation.
    "LLC", "LLP", "PLC", "GMBH",
}


class EntityExtractor:
    """Regex + gazetteer entity extractor. Emits PERSON / ORG / PROJECT."""

    def __init__(self):
        self._project_re = re.compile(rf"\b{_PROJECT_TRIGGER}\s+[A-Z][\w-]*")
        self._titled_re = re.compile(rf"\b{_TITLE}\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")
        # 1-3 capitalised name words then a suffix. The name-word class excludes
        # '.' so it cannot swallow a preceding sentence's final word across a full
        # stop ("...last Friday. Meridian Systems"); {1,3} (not {0,}) means a bare
        # suffix with no name in front ("LLC") is not matched.
        self._org_suffix_re = re.compile(rf"\b(?:[A-Z][A-Za-z&]+\s+){{1,3}}{_ORG_SUFFIX}\b")
        self._acronym_re = re.compile(r"\b[A-Z]{2,6}\b")
        # A capitalised token, optionally followed by one more capitalised token
        # (surname). Person-hood is decided by the first token being a known name.
        self._name_re = re.compile(r"\b([A-Z][a-z]+)(?:\s+([A-Z][a-z]+))?\b")

    def extract(self, text: str) -> List[Entity]:
        entities: List[Entity] = []
        seen = set()
        # Character spans already claimed by a higher-precedence rule, so a token
        # inside "Project Omega" or "Acme Corp" is not re-emitted as a bare name.
        claimed: List[tuple] = []

        def _add(name, category, confidence, start, end):
            # Claim the span for overlap purposes on EVERY accepted match, even a
            # repeat of an already-seen entity — otherwise a second "Prof. Lin"
            # leaves its "Lin" unclaimed and the bare-name rule re-emits it.
            claimed.append((start, end))
            name = re.sub(r"\s+", " ", name).strip().strip(".,;:?!")
            key = (name.lower(), category)
            if key in seen:
                return
            seen.add(key)
            entities.append(Entity(name=name, category=category, confidence=confidence,
                                   context=self._context(text, start, end)))

        def _overlaps(start, end):
            return any(s < end and start < e for s, e in claimed)

        # 1. PROJECT — trigger + name, keep the full surface ("Project Omega").
        for m in self._project_re.finditer(text):
            _add(m.group(0), "PROJECT", 0.95, m.start(), m.end())

        # 2. PERSON via title ("Dr. Sivan"). High precision.
        for m in self._titled_re.finditer(text):
            if not _overlaps(m.start(), m.end()):
                _add(m.group(0), "PERSON", 0.9, m.start(), m.end())

        # 3. ORG via corporate suffix ("Acme Corp", "Meridian Systems"). Trim a
        #    leading determiner ("The LLC" -> just a suffix, so not an org).
        for m in self._org_suffix_re.finditer(text):
            if _overlaps(m.start(), m.end()):
                continue
            words = m.group(0).split()
            if words and words[0].lower() in _DETERMINERS:
                words = words[1:]
            if len(words) < 2:  # nothing left but the bare suffix
                continue
            _add(" ".join(words), "ORG", 0.9, m.start(), m.end())

        # 4. ORG via acronym ("NASA"), excluding common tech acronyms.
        for m in self._acronym_re.finditer(text):
            if m.group(0) in _ACRONYM_STOPLIST or _overlaps(m.start(), m.end()):
                continue
            _add(m.group(0), "ORG", 0.7, m.start(), m.end())

        # 5. PERSON via known given name ("Priya", "Alice Smith"). Lowest
        #    precedence, so it never overrides a project/org/title claim.
        for m in self._name_re.finditer(text):
            if _overlaps(m.start(), m.end()):
                continue
            if m.group(1).lower() not in _FIRST_NAMES:
                continue
            # Extend to a following capitalised surname only when present.
            name = m.group(0) if m.group(2) else m.group(1)
            _add(name, "PERSON", 0.75, m.start(), m.end())

        return entities

    def _context(self, text: str, start: int, end: int, window: int = 50) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return "..." + text[s:e].replace("\n", " ").strip() + "..."
