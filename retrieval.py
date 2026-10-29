"""Document retrieval. Optional semantic dependencies degrade to lexical search."""
from __future__ import annotations
from dataclasses import dataclass
import re
from collections import Counter
from document_processor import Chunk

@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    page_number: int
    source: str
    score: float
    chunk_id: str

class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.mode = 'lexical fallback'
        self._collection = None
        self._embedder = None
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            client = chromadb.Client()
            self._collection = client.create_collection(name=f'research_{id(self)}')
            vectors = self._embedder.encode([c.text for c in chunks]).tolist()
            self._collection.add(ids=[c.chunk_id for c in chunks], documents=[c.text for c in chunks], metadatas=[{'page': c.page_number, 'source': c.source} for c in chunks], embeddings=vectors)
            self.mode = 'ChromaDB + sentence-transformers'
        except Exception:
            self._collection = None

    @staticmethod
    def _tokens(text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9']+", text.lower())
        # A deliberately small normalization keeps the dependency-free fallback
        # useful for ordinary singular/plural question variations.
        return [token[:-1] if len(token) > 4 and token.endswith('s') else token for token in tokens]

    def search(self, query: str, k: int = 4) -> list[RetrievedChunk]:
        if not query.strip() or not self.chunks:
            return []
        if self._collection is not None and self._embedder is not None:
            vector = self._embedder.encode([query]).tolist()
            data = self._collection.query(query_embeddings=vector, n_results=min(k, len(self.chunks)))
            return [RetrievedChunk(t, int(m['page']), m['source'], 1.0 / (1.0 + float(d)), next(c.chunk_id for c in self.chunks if c.text == t and c.page_number == int(m['page']))) for t, m, d in zip(data['documents'][0], data['metadatas'][0], data['distances'][0])]
        q = Counter(self._tokens(query)); scored = []
        for c in self.chunks:
            tokens = Counter(self._tokens(c.text)); overlap = sum(min(n, tokens[t]) for t, n in q.items())
            phrase_bonus = 2 if query.lower() in c.text.lower() else 0
            scored.append((overlap + phrase_bonus, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [RetrievedChunk(c.text, c.page_number, c.source, float(score), c.chunk_id) for score, c in scored[:k] if score > 0] or [RetrievedChunk(c.text, c.page_number, c.source, 0.0, c.chunk_id) for c in self.chunks[:k]]
