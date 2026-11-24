import ollama
import json
import re
import time
from dataclasses import dataclass, field
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from upii.core.config import config
from upii.core.types import Chunk
from upii.core.errors import ModelError

PROVIDERS = ("local", "remote")

# The model's abstention signal, and the message shown in its place.
NOT_FOUND_TOKEN = "NOT_FOUND"
NOT_FOUND_MESSAGE = "Not found in your memory."
_NOT_FOUND_RE = re.compile(r"\bNOT_FOUND\b")
_NOT_FOUND_VARIANT_RE = re.compile(r"\bNOT[ -]?FOUND\b")  # NOT FOUND, NOT-FOUND, NOTFOUND
_CITATION_RE = re.compile(r"\[(\d{1,3})\]")


def estimate_tokens(text: Optional[str]) -> int:
    """Rough token count when the model reports none: about 4 characters per token, at least 1."""
    return max(1, len(text or "") // 4)


@dataclass
class Usage:
    """Tokens and latency of one model call. Holds counts only, never prompt or answer text.

    ``input_tokens`` / ``output_tokens`` come from the model response (Ollama
    ``prompt_eval_count`` / ``eval_count``; Gemini ``usageMetadata.promptTokenCount`` /
    ``candidatesTokenCount``). When the response carries no count (mock mode, an error
    reply), :func:`estimate_tokens` fills it in and ``estimated`` is True.
    ``latency_ms`` is wall-clock time around the call, retries included.
    """
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str
    estimated: bool

    def to_dict(self) -> Dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "latency_ms": self.latency_ms, "model": self.model, "estimated": self.estimated}


@dataclass
class Answer:
    """Result of :meth:`LocalLLM.answer`."""
    text: str
    found: bool
    cited: List[int] = field(default_factory=list)  # 1-based indices into the chunks given
    usage: Optional[Usage] = None  # None when no model was called


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
        self._gemini_usage: Optional[Dict] = None  # usageMetadata of the last Gemini reply

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
                self._gemini_usage = result.get('usageMetadata') if isinstance(result, dict) else None
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
        return self._generate_with_usage(prompt)[0]

    def _generate_with_usage(self, prompt: str) -> Tuple[str, Usage]:
        """Model text plus the :class:`Usage` of the call that produced it."""
        start = time.perf_counter()
        text, counts = self._generate_raw(prompt)
        latency_ms = int(round((time.perf_counter() - start) * 1000))
        n_in, n_out = counts
        estimated = n_in is None or n_out is None
        if n_in is None:
            n_in = estimate_tokens(prompt)
        if n_out is None:
            n_out = estimate_tokens(text)
        # model_info() is read after the call: Ollama can drop to mock mid-call.
        return text, Usage(input_tokens=int(n_in), output_tokens=int(n_out), latency_ms=latency_ms,
                           model=self.model_info()["name"], estimated=estimated)

    @staticmethod
    def _count(value) -> Optional[int]:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    def _generate_raw(self, prompt: str) -> Tuple[str, Tuple[Optional[int], Optional[int]]]:
        """Model text and the (input, output) token counts the response reports, or None each."""
        if self.use_gemini:
            self._gemini_usage = None
            text = self._call_gemini(prompt)
            meta = self._gemini_usage if isinstance(self._gemini_usage, dict) else {}
            return text, (self._count(meta.get("promptTokenCount")),
                          self._count(meta.get("candidatesTokenCount")))

        if self.is_mock:
            return "This is a simulated AI response (Ollama not connected).", (None, None)

        try:
            response = ollama.generate(model=self.model, prompt=prompt)
        except Exception as e_gpu:
            try:
                print(f"[WARN] GPU Generation failed ({e_gpu}). Retrying with CPU only...")
                response = ollama.generate(model=self.model, prompt=prompt, options={'num_gpu': 0})
            except Exception:
                print(f"[WARN] Generation failed. System entering Mock Mode resiliency.")
                self.is_mock = True
                return "This is a simulated AI response (Ollama failed).", (None, None)
        return response['response'], (self._count(response.get('prompt_eval_count')),
                                       self._count(response.get('eval_count')))

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

        Uppercase variants ("NOT FOUND", "NOT-FOUND") are also treated as abstentions
        when the answer cites no source. A cited variant (e.g. "404 NOT FOUND [1]")
        survives because the citation proves it is quoting a document, not declining.
        """
        if not chunks:
            return Answer(text=NOT_FOUND_MESSAGE, found=False, cited=[])
        text, usage = self._generate_with_usage(self._answer_prompt(question, chunks))
        raw = (text or "").strip()
        # The model was called, so even an abstention carries its usage.
        if _NOT_FOUND_RE.search(raw):
            return Answer(text=NOT_FOUND_MESSAGE, found=False, cited=[], usage=usage)
        cited = sorted({int(n) for n in _CITATION_RE.findall(raw) if 1 <= int(n) <= len(chunks)})
        # Uppercase NOT FOUND / NOT-FOUND without citations -> abstain.
        if not cited and _NOT_FOUND_VARIANT_RE.search(raw):
            return Answer(text=NOT_FOUND_MESSAGE, found=False, cited=[], usage=usage)
        return Answer(text=raw, found=True, cited=cited, usage=usage)

    def answer_with_citations(self, question: str, chunks: List[Chunk]) -> str:
        """Generates an answer using the provided chunks as context (raw model text)."""
        return self.generate(self._answer_prompt(question, chunks))
