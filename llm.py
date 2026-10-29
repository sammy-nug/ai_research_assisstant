"""Local Ollama client and transparent non-LLM fallback."""
from __future__ import annotations
import os, re, json, urllib.request
from prompts import SUMMARY_PROMPT, QA_PROMPT, format_evidence

class LocalLLM:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
        self.base_url = (base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')).rstrip('/')
        self.last_status = 'Fallback mode: Ollama not checked yet.'

    def _generate(self, prompt: str) -> str | None:
        payload = json.dumps({'model': self.model, 'prompt': prompt, 'stream': False}).encode()
        try:
            req = urllib.request.Request(self.base_url + '/api/generate', data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=45) as response:
                result = json.loads(response.read().decode())
            self.last_status = f'Ollama model: {self.model}'
            return result.get('response', '').strip() or None
        except Exception as exc:
            self.last_status = f'Fallback mode: Ollama unavailable ({type(exc).__name__}).'
            return None

    def summarize(self, chunks, detailed: bool = False) -> str:
        evidence = format_evidence(chunks[:12])
        answer = self._generate(SUMMARY_PROMPT + (' Provide a detailed response.' if detailed else ' Keep it concise.') + '\n\n' + evidence)
        if answer: return answer
        sentences = re.split(r'(?<=[.!?])\s+', ' '.join(c.text for c in chunks))
        selected = sentences[:8 if detailed else 4]
        return ' '.join(selected) + ('\n\nThis extractive summary was produced locally because Ollama is unavailable.' if selected else 'No summary could be produced.')

    def answer(self, question: str, chunks) -> str:
        evidence = format_evidence(chunks)
        answer = self._generate(QA_PROMPT.format(question=question, evidence=evidence))
        if answer: return answer
        qwords = set(re.findall(r"[a-zA-Z0-9']+", question.lower())) - {'what','why','how','when','where','which','does','did','is','are','the','a','an','of','to','in'}
        best = [c for c in chunks if qwords & set(re.findall(r"[a-zA-Z0-9']+", c.text.lower()))]
        if not best: return "I don't have enough evidence in the uploaded document to answer that question."
        return ' '.join(c.text for c in best[:2])
