"""NOVEL COMPONENT 3 — IRT-calibrated difficulty.

Most QG systems ask an LLM "is this easy/medium/hard?". CAL-QG instead
  (1) fits a Rasch (1-PL IRT) model on real student responses to get item difficulty b,
  (2) learns a regressor  text-features -> b  from calibrated items,
  (3) uses it to predict difficulty for NEW, never-answered questions.
Before any response data exists it falls back to a transparent heuristic prior.
"""
import math, re
import numpy as np
from sklearn.linear_model import Ridge
from .bloom import classify, level_index


def fit_rasch(R, iters=2000, lr=1.0):
    """R: students x items matrix of {0,1,nan}. Returns (theta, b). Joint MLE, gradient ascent."""
    R = np.asarray(R, float)
    mask = ~np.isnan(R)
    Y = np.nan_to_num(R)
    th, b = np.zeros(R.shape[0]), np.zeros(R.shape[1])
    for _ in range(iters):
        P = 1 / (1 + np.exp(-(th[:, None] - b[None, :])))
        G = (Y - P) * mask
        th += lr * G.sum(1) / np.maximum(mask.sum(1), 1)     # mean gradients: stable for any class size
        b -= lr * G.sum(0) / np.maximum(mask.sum(0), 1)
        th = np.clip(th, -4, 4); b = np.clip(b, -4, 4)
        b -= b.mean()                       # identifiability: mean item difficulty = 0
    return th, b


class DifficultyModel:
    def __init__(self, embedder=None):
        self.emb, self.reg, self.calibrated = embedder, None, False

    def features(self, q):
        text = q["question"]
        toks = re.findall(r"[a-zA-Z]+", text.lower())
        idf = np.mean([self.emb.idf(t) for t in toks]) if (self.emb and toks) else 1.0
        bloom = level_index(classify(text)[0]) / 5
        ans_len = math.log1p(len(q.get("answer", "").split()))
        concepts = len(q.get("concepts", [q.get("concept")]))
        return np.array([bloom, math.log1p(len(toks)), ans_len, idf / 10, concepts], float)

    def predict_b(self, q):
        f = self.features(q)
        if self.calibrated:
            return float(self.reg.predict(f[None])[0])
        # heuristic prior, centred near 0 on the logit scale
        return float(3.0 * f[0] + 0.4 * f[2] + 0.3 * f[3] + 0.3 * (f[4] - 1) - 2.1)

    def calibrate(self, questions, responses):
        """questions: list of question dicts (items, in column order); responses: students x items."""
        _, b = fit_rasch(responses)
        X = np.stack([self.features(q) for q in questions])
        self.reg = Ridge(alpha=1.0).fit(X, b)
        self.calibrated = True
        return b

    @staticmethod
    def to_unit(b):           # logit difficulty -> [0,1]
        return 1 / (1 + math.exp(-b))

    @staticmethod
    def label(u):
        return "Easy" if u < 0.4 else ("Medium" if u < 0.65 else "Hard")
