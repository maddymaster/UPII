
import re
from typing import List, Tuple, Dict
from dataclasses import dataclass

@dataclass
class Entity:
    name: str
    category: str
    confidence: float
    context: str

class EntityExtractor:
    """Lightweight rule-based entity extractor."""
    
    def __init__(self):
        # Pre-compile regex patterns for performance
        self.patterns = {
            "PROJECT": [
                re.compile(r"\b(Project|Operation|Code Name|Codename)\s+([A-Z][a-zA-Z0-9_-]+)", re.IGNORECASE),
                re.compile(r"\b(Team|Squad)\s+([A-Z][a-zA-Z0-9_-]+)", re.IGNORECASE)
            ],
            # Strict capitalization chaining for potential Names/Orgs (e.g. "Alice Smith", "Acme Corp")
            # Avoids single words to reduce noise, looks for 2+ capitalized words
            "TOPIC": [
                re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
            ]
        }
        
    def extract(self, text: str) -> List[Entity]:
        """Extract entities from text chunk."""
        entities = []
        seen = set()
        
        # 1. Project Extraction (High Confidence)
        for pattern in self.patterns["PROJECT"]:
            for match in pattern.finditer(text):
                # Group 2 is the actual name (e.g. "Omega" from "Project Omega")
                full_match = match.group(0) # Context
                name = match.group(2)
                # Cleaning
                name = name.strip(".,;:?!")
                
                key = (name, "PROJECT")
                if key not in seen:
                    entities.append(Entity(
                        name=name, 
                        category="PROJECT", 
                        confidence=0.9, 
                        context=self._get_context(text, match.start(), match.end())
                    ))
                    seen.add(key)

        # 2. Topic/Person Extraction (Medium Confidence)
        # Only if strict chaining is found
        # Trigger words that introduce a PROJECT/TEAM; a TOPIC match that merely
        # restates one (e.g. "Project Omega", "Team Alpha") is a duplicate of the
        # PROJECT entity already captured, so skip it rather than add noise.
        _project_triggers = ("project", "operation", "code name", "codename", "team", "squad")

        for pattern in self.patterns["TOPIC"]:
            for match in pattern.finditer(text):
                name = match.group(1)
                # Filter out likely common phrases or start of sentences if needed
                # For now, accept all multi-word capitalized sequences

                # Skip phrases that just re-state a PROJECT/TEAM trigger.
                if name.lower().startswith(_project_triggers):
                    continue

                # Check it's not already found as a Project
                if (name, "PROJECT") in seen:
                    continue

                key = (name, "TOPIC")
                if key not in seen:
                    entities.append(Entity(
                        name=name, 
                        category="TOPIC",   # Could be Person or Org, genericizing to TOPIC
                        confidence=0.6,
                        context=self._get_context(text, match.start(), match.end())
                    ))
                    seen.add(key)
        
        return entities

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get a snippet of text around the match."""
        s = max(0, start - window)
        e = min(len(text), end + window)
        return "..." + text[s:e].replace("\n", " ").strip() + "..."
