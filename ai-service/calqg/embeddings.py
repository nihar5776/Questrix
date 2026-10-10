"""Embedding backend: Sentence-Transformers if installed, else TF-IDF (fully offline)."""
import numpy as np


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.kind = "tfidf"
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

    def encode(self, texts, batch_size: int = 32):
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.zeros((0, 384 if self.kind == "sbert" else 100), dtype=np.float32)

        if self.kind == "sbert":
            try:
                v = self.model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
                return np.asarray(v, dtype=np.float32)
            except Exception:
                # Fallback to smaller batch size if memory is constrained
                v = self.model.encode(texts, batch_size=max(1, batch_size // 4), normalize_embeddings=True, show_progress_bar=False)
                return np.asarray(v, dtype=np.float32)

        v = self.model.transform(texts).toarray().astype(np.float32)
        n = np.linalg.norm(v, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return v / n

    def idf(self, token: str) -> float:
        if self.kind != "tfidf":
            return 1.0
        vocab = getattr(self.model, "vocabulary_", {})
        return float(self.model.idf_[vocab[token]]) if token in vocab else float(getattr(self.model, "idf_", np.array([1.0])).max())


def cosine(a, b) -> float:
    return float(np.dot(a, b))
