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

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        if self.kind == "sbert":
            v = self.model.encode(texts, normalize_embeddings=True)
            return np.asarray(v, dtype=np.float32)
        v = self.model.transform(texts).toarray().astype(np.float32)
        n = np.linalg.norm(v, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return v / n

    def idf(self, token: str) -> float:
        if self.kind != "tfidf":
            return 1.0
        vocab = self.model.vocabulary_
        return float(self.model.idf_[vocab[token]]) if token in vocab else float(self.model.idf_.max())


def cosine(a, b) -> float:
    return float(np.dot(a, b))
