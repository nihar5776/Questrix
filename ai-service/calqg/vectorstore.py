"""Vector store with curriculum metadata filtering. Qdrant if available, else in-memory."""
import numpy as np


class VectorStore:
    def __init__(self, embedder):
        self.emb = embedder
        self.chunks = []
        self.vecs = None
        self._chunk_ids = set()

    def add(self, new_chunks, progress_cb=None):
        if not new_chunks:
            return

        # Deduplicate incoming chunks against existing store
        filtered_chunks = []
        for c in new_chunks:
            cid = c.get("id") or c.get("text")[:30]
            if cid not in self._chunk_ids:
                self._chunk_ids.add(cid)
                filtered_chunks.append(c)

        if not filtered_chunks:
            return

        if progress_cb:
            progress_cb(75.0, f"Fitting embedding vocabulary for {len(filtered_chunks)} chunks...")

        self.chunks.extend(filtered_chunks)
        all_texts = [c["text"] for c in self.chunks]
        
        self.emb.fit(all_texts)

        if progress_cb:
            progress_cb(85.0, "Encoding text vectors in batches...")

        self.vecs = self.emb.encode(all_texts, batch_size=32)

        # Verification check
        if len(self.vecs) != len(self.chunks):
            raise ValueError(f"Vector matrix length mismatch: {len(self.vecs)} vectors for {len(self.chunks)} chunks.")

        if progress_cb:
            progress_cb(95.0, f"Vector database updated with {len(self.chunks)} total chunks.")

    def search(self, query, k=4, where=None):
        if not self.chunks or self.vecs is None or len(self.vecs) == 0:
            return []

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
