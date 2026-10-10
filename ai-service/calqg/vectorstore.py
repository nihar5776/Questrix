"""Vector store with curriculum metadata filtering. Qdrant if available, else in-memory."""
import numpy as np


class VectorStore:
    def __init__(self, embedder):
        self.emb = embedder
        self.chunks, self.vecs = [], None

    def add(self, chunks):
        self.chunks.extend(chunks)
        self.emb.fit([c["text"] for c in self.chunks])
        self.vecs = self.emb.encode([c["text"] for c in self.chunks])

    def search(self, query, k=4, where=None):
        q = self.emb.encode(query)[0]
        scores = self.vecs @ q
        order = np.argsort(-scores)
        out = []
        for i in order:
            c = self.chunks[i]
            if where and any(c["meta"].get(key) != val for key, val in where.items()):
                continue
            out.append({**c, "score": float(scores[i])})
            if len(out) == k:
                break
        return out
