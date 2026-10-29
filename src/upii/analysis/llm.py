import ollama
import json
import re
from dataclasses import dataclass, field
import urllib.request
import urllib.error
from typing import Dict, List, Optional
from upii.core.config import config
from upii.core.types import Chunk
from upii.core.errors import ModelError

PROVIDERS = ("local", "remote")

# The model's abstention signal, and the message shown in its place.
NOT_FOUND_TOKEN = "NOT_FOUND"
NOT_FOUND_MESSAGE = "Not found in your memory."
_NOT_FOUND_RE = re.compile(r"\bNOT_FOUND\b")
_CITATION_RE = re.compile(r"\[(\d{1,3})\]")


@dataclass
class Answer:
    """Result of :meth:`LocalLLM.answer`."""
    text: str
    found: bool
    cited: List[int] = field(default_factory=list)  # 1-based indices into the chunks given


class LocalLLM:
    """Interface to Inference: Ollama on this machine, or Gemini when explicitly chosen."""

    def __init__(self, provider: Optional[str] = None):
        """``provider`` overrides ``config.llm_provider`` ("local" | "remote").

        Remote (Gemini) is used only when the provider is "remote"; a GEMINI_API_KEY
        alone never routes answers off the machine. Asking for remote without a key
        raises :class:`ModelError` rather than quietly answering locally.
        """
        self.provider = str(provider or getattr(config, "llm_provider", "local") or "local").strip().lower()
        if self.provider not in PROVIDERS:
            raise ModelError(f"llm_provider must be 'local' or 'remote', got {self.provider!r}")
        self.model = config.llm_model
        self.gemini_key = getattr(config, 'gemini_api_key', None)
        self.gemini_model = getattr(config, 'gemini_model', 'gemini-1.5-flash')
        self.is_mock = False

        self.use_gemini = self.provider == "remote"
        if self.use_gemini and not (self.gemini_key and self.gemini_key not in ("", "YOUR_API_KEY")):
            raise ModelError("llm_provider is 'remote' but GEMINI_API_KEY is not set")

        if not self.use_gemini:
            self._check_ollama_connection()

    def model_info(self) -> Dict[str, str]:
        """The model that answers (read after generating: Ollama can drop to mock mid-call)."""
        if self.use_gemini:
            return {"name": self.gemini_model, "provider": "gemini", "location": "remote"}
        if self.is_mock:
            return {"name": "mock", "provider": "mock", "location": "local"}
        return {"name": self.model, "provider": "ollama", "location": "local"}

    def model_label(self) -> str:
        """``"llama3.2 (ollama, local)"`` — for CLI output."""
        m = self.model_info()
        return f"{m['name']} ({m['provider']}, {m['location']})"

    def _check_ollama_connection(self):
        try:
            ollama.list()
        except:
            self.is_mock = True

    def _call_gemini(self, prompt: str) -> str:
        """Calls Google Gemini API via REST (Standard Lib)."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                # Extract text from Candidate -> Content -> Parts
                try:
                    return result['candidates'][0]['content']['parts'][0]['text']
                except (KeyError, IndexError):
                    return "Error: Empty or malformed response from Gemini."
        except urllib.error.HTTPError as e:
            # Surface the actual API message (e.g. "API key expired") instead of just the status.
            detail = e.reason
            try:
                body = json.loads(e.read().decode('utf-8'))
                detail = body.get('error', {}).get('message', detail)
            except Exception:
                pass
            return f"Gemini API Error: {e.code} {detail}"
        except Exception as e:
            return f"Connection Failed: {e}"

    def generate(self, prompt: str) -> str:
        if self.use_gemini:
            return self._call_gemini(prompt)

        if self.is_mock:
            return "This is a simulated AI response (Ollama not connected)."
            
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            return response['response']
        except Exception as e_gpu:
            try:
                print(f"[WARN] GPU Generation failed ({e_gpu}). Retrying with CPU only...")
                response = ollama.generate(model=self.model, prompt=prompt, options={'num_gpu': 0})
                return response['response']
            except Exception:
                print(f"[WARN] Generation failed. System entering Mock Mode resiliency.")
                self.is_mock = True
                return "This is a simulated AI response (Ollama failed)."

    def _answer_prompt(self, question: str, chunks: List[Chunk]) -> str:
        context_str = ""
        if chunks:
            for i, chunk in enumerate(chunks):
                context_str += f"Source [{i+1}] (ID: {chunk.doc_hash}):\n{chunk.text}\n---\n"
        else:
            context_str = "No specific local files found."

        # Adaptive Prompt based on engine
        system_instruction = "You are my second brain. You are me, but with perfect memory."
        if self.use_gemini:
            system_instruction += " Speak in my voice: direct, professional, and concise. Do not sound like a generic AI assistant."

        return f"""{system_instruction}

Context from my digital life:
{context_str}

User/My Query: {question}

Instructions:
1. Answer using the context provided as your primary memory.
2. If drafting content, adopt the style found in the context.
3. If the context does not contain the answer, reply with exactly {NOT_FOUND_TOKEN} and nothing else. Do not guess.
4. NEVER say "As an AI" or "I am a large language model" or mention "Gemini". You are my Second Brain.
5. CITE YOUR SOURCES like [1] only if you are referencing specific facts from my files.
6. Be concise, direct, and helpful.

Answer:"""

    def answer(self, question: str, chunks: List[Chunk]) -> "Answer":
        """Grounded answer with a structured abstention flag and the sources it cites.

        No context -> not found, and the model is never called. Otherwise the model
        is told to reply with ``NOT_FOUND`` when the context lacks the answer; that
        token (not any particular wording) sets ``found=False``. ``cited`` holds the
        1-based source numbers the answer actually references, so callers list only
        those — never citations for an answer that has none.
        """
        if not chunks:
            return Answer(text=NOT_FOUND_MESSAGE, found=False, cited=[])
        raw = (self.generate(self._answer_prompt(question, chunks)) or "").strip()
        if _NOT_FOUND_RE.search(raw):
            return Answer(text=NOT_FOUND_MESSAGE, found=False, cited=[])
        cited = sorted({int(n) for n in _CITATION_RE.findall(raw) if 1 <= int(n) <= len(chunks)})
        return Answer(text=raw, found=True, cited=cited)

    def answer_with_citations(self, question: str, chunks: List[Chunk]) -> str:
        """Generates an answer using the provided chunks as context (raw model text)."""
        return self.generate(self._answer_prompt(question, chunks))
