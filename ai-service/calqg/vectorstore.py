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
            if progress_cb:
                progress_cb(95.0, "All chunks already indexed in vector database.")
            return

        new_texts = [c["text"] for c in filtered_chunks]

        if progress_cb:
            progress_cb(75.0, f"Fitting embedding vocabulary for {len(filtered_chunks)} new chunks...")

        # If TF-IDF, fit on all texts; no-op for neural embeddings
        self.chunks.extend(filtered_chunks)
        all_texts = [c["text"] for c in self.chunks]
        self.emb.fit(all_texts)

        if progress_cb:
            progress_cb(78.0, f"Encoding {len(filtered_chunks)} new chunks in batches...")

        # Encode only the new chunks incrementally!
        new_vecs = self.emb.encode(
            new_texts, 
            batch_size=64, 
            progress_cb=progress_cb, 
            start_pct=80.0, 
            end_pct=95.0
        )

        if self.vecs is None or len(self.vecs) == 0:
            self.vecs = new_vecs
        else:
            self.vecs = np.vstack([self.vecs, new_vecs])

        # Verification check
        if len(self.vecs) != len(self.chunks):
            raise ValueError(f"Vector matrix length mismatch: {len(self.vecs)} vectors for {len(self.chunks)} chunks.")

        if progress_cb:
            progress_cb(96.0, f"Vector database updated successfully. Stored {len(self.chunks)} total chunks.")

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
