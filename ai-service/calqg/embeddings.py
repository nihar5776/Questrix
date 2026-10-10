"""Embedding backend: Sentence-Transformers if installed, else TF-IDF (fully offline).
Supports explicit batch-by-batch inference with PyTorch no_grad() and progress callbacks."""
import numpy as np


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.kind = "tfidf"
        self.model = None
        self._fitted = False
        
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.kind = "sbert"
        except Exception:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.model = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True,
                                         stop_words="english")
            self._fitted = False

    def fit(self, corpus):
        """TF-IDF needs the corpus vocabulary; no-op for neural embeddings."""
        if self.kind == "tfidf":
            self.model.fit(corpus)
            self._fitted = True

    def encode(self, texts, batch_size: int = 64, progress_cb=None, start_pct: float = 80.0, end_pct: float = 95.0):
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.zeros((0, 384 if self.kind == "sbert" else 100), dtype=np.float32)

        total = len(texts)

        if self.kind == "sbert":
            # Attempt torch.no_grad() context for memory efficiency & faster inference
            try:
                import torch
                no_grad_ctx = torch.no_grad()
            except Exception:
                class DummyCtx:
                    def __enter__(self): pass
                    def __exit__(self, *args): pass
                no_grad_ctx = DummyCtx()

            embeddings_list = []
            num_batches = (total + batch_size - 1) // batch_size

            with no_grad_ctx:
                for i in range(0, total, batch_size):
                    batch_texts = texts[i : i + batch_size]
                    batch_idx = (i // batch_size) + 1
                    
                    try:
                        b_vecs = self.model.encode(
                            batch_texts, 
                            batch_size=len(batch_texts), 
                            normalize_embeddings=True, 
                            show_progress_bar=False
                        )
                        embeddings_list.append(np.asarray(b_vecs, dtype=np.float32))
                    except MemoryError:
                        # Handle memory constraint by falling back to mini-batches of 16
                        sub_list = []
                        for sub_i in range(0, len(batch_texts), 16):
                            sub_batch = batch_texts[sub_i : sub_i + 16]
                            sub_v = self.model.encode(
                                sub_batch,
                                batch_size=len(sub_batch),
                                normalize_embeddings=True,
                                show_progress_bar=False
                            )
                            sub_list.append(np.asarray(sub_v, dtype=np.float32))
                        embeddings_list.append(np.vstack(sub_list))

                    if progress_cb and total > 0:
                        pct = start_pct + (batch_idx / num_batches) * (end_pct - start_pct)
                        processed_count = min(i + len(batch_texts), total)
                        progress_cb(
                            pct, 
                            f"Encoding text vectors (batch {batch_idx}/{num_batches}, {processed_count}/{total} chunks)"
                        )

            return np.vstack(embeddings_list)

        # TF-IDF Fallback
        if not self._fitted:
            self.fit(texts)

        num_batches = (total + batch_size - 1) // batch_size
        embeddings_list = []

        for i in range(0, total, batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_idx = (i // batch_size) + 1

            v = self.model.transform(batch_texts).toarray().astype(np.float32)
            n = np.linalg.norm(v, axis=1, keepdims=True)
            n[n == 0] = 1.0
            embeddings_list.append(v / n)

            if progress_cb and total > 0:
                pct = start_pct + (batch_idx / num_batches) * (end_pct - start_pct)
                processed_count = min(i + len(batch_texts), total)
                progress_cb(
                    pct, 
                    f"Encoding text vectors (batch {batch_idx}/{num_batches}, {processed_count}/{total} chunks)"
                )

        return np.vstack(embeddings_list)

    def idf(self, token: str) -> float:
        if self.kind != "tfidf":
            return 1.0
        vocab = getattr(self.model, "vocabulary_", {})
        return float(self.model.idf_[vocab[token]]) if token in vocab else float(getattr(self.model, "idf_", np.array([1.0])).max())


def cosine(a, b) -> float:
    return float(np.dot(a, b))
