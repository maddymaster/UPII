import ollama
import json
import urllib.request
import urllib.error
from typing import List, Optional
from upii.core.config import config
from upii.core.types import Chunk
from upii.core.errors import ModelError

class LocalLLM:
    """Interface to Inference (Gemini or Ollama)."""
    
    def __init__(self):
        self.model = config.llm_model
        self.gemini_key = getattr(config, 'gemini_api_key', None)
        self.gemini_model = getattr(config, 'gemini_model', 'gemini-1.5-flash')
        self.is_mock = False
        
        # Prefer Gemini if a real key is present (supports both "AIza..." and "AQ...." key formats)
        self.use_gemini = bool(self.gemini_key and self.gemini_key not in ("", "YOUR_API_KEY"))
        
        if not self.use_gemini:
            self._check_ollama_connection()

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

    def answer_with_citations(self, question: str, chunks: List[Chunk]) -> str:
        """Generates an answer using the provided chunks as context."""
        
        # If no context, we still might want to answer if using Gemini (General Knowledge),
        # but for RAG we usually restrict. However, user wants "better than I don't know".
        # We will try to answer but flag it if no context.
        # BUT the logic below depends on context.
        
        context_str = ""
        if chunks:
            for i, chunk in enumerate(chunks):
                # source = f"{chunk.doc_hash} (Chunk {chunk.chunk_hash})"
                context_str += f"Source [{i+1}] (ID: {chunk.doc_hash}):\n{chunk.text}\n---\n"
        else:
            context_str = "No specific local files found."

        # Adaptive Prompt based on engine
        system_instruction = "You are my second brain. You are me, but with perfect memory."
        if self.use_gemini:
            system_instruction += " Speak in my voice: direct, professional, and concise. Do not sound like a generic AI assistant."

        prompt = f"""{system_instruction}

Context from my digital life:
{context_str}

User/My Query: {question}

Instructions:
1. Answer using the context provided as your primary memory.
2. If drafting content, adopt the style found in the context.
3. If the question is generic (e.g. "What is AI?"), answer it, but ground it in my perspective/interests if the context allows.
4. NEVER say "As an AI" or "I am a large language model" or mention "Gemini". You are my Second Brain.
5. CITE YOUR SOURCES like [1] only if you are referencing specific facts from my files.
6. Be concise, direct, and helpful.

Answer:"""

        return self.generate(prompt)
