import re
import uuid
from typing import List, Tuple
from upii.core.types import Chunk, Task

class TaskExtractor:
    """Extracts tasks from text using heuristics."""
    
    # Patterns for tasks
    TASK_PATTERNS = [
        r"(?i)\bTODO[:\s]+(.*)",
        r"(?i)\bFIXME[:\s]+(.*)",
        r"-\s*\[\s*\]\s*(.*)",  # - [ ] Task
        r"\*\s*\[\s*\]\s*(.*)", # * [ ] Task
        r"(?i)\bAction Item[:\s]+(.*)",
    ]

    def extract(self, chunks: List[Chunk]) -> List[Task]:
        tasks = []
        for chunk in chunks:
            # 1. Classify (Simple heuristic for now, could be LLM later)
            category = self._classify(chunk.text)
            chunk.category = category # Tag in memory
            
            # 2. Extract Tasks
            lines = chunk.text.split('\n')
            for line in lines:
                for pattern in self.TASK_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        description = match.group(1).strip()
                        if len(description) > 3: # Noise filter
                             tasks.append(Task(
                                 task_id=str(uuid.uuid4()),
                                 description=description,
                                 status="pending",
                                 source_chunk_id=chunk.chunk_hash,
                                 source_doc_id=chunk.doc_hash
                             ))
                        break # Only match first pattern per line
        return tasks

    def _classify(self, text: str) -> str:
        """Heuristic classification."""
        text_lower = text.lower()
        if "decision:" in text_lower or "decided:" in text_lower:
            return "decision"
        if "todo" in text_lower or "- [ ]" in text_lower:
            return "task"
        return "note"
