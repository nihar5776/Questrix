"""Rule-based Bloom classifier (Anderson & Krathwohl revised taxonomy verb lists).
Deterministic, so the Bloom *validator* does not rely on the LLM judging itself."""
import re
from .config import BLOOM_LEVELS

VERBS = {
    "Remember":   ["define", "list", "state", "name", "recall", "identify", "what is", "label"],
    "Understand": ["explain", "describe", "summarize", "interpret", "illustrate", "discuss", "classify"],
    "Apply":      ["write", "implement", "apply", "use", "demonstrate", "compute", "solve", "modify"],
    "Analyze":    ["differentiate", "compare", "contrast", "analyze", "analyse", "distinguish", "examine"],
    "Evaluate":   ["justify", "evaluate", "assess", "critique", "argue", "defend", "which is better"],
    "Create":     ["design", "create", "develop", "propose", "construct", "formulate", "build"],
}


def classify(question: str):
    """Returns (level, confidence). Leading verb counts double: it signals intent."""
    q = question.lower().strip()
    scores = {lvl: 0.0 for lvl in BLOOM_LEVELS}
    for lvl, verbs in VERBS.items():
        for v in verbs:
            if q.startswith(v):
                scores[lvl] += 2.0
            elif re.search(r"\b" + re.escape(v) + r"\b", q):
                scores[lvl] += 1.0
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if total == 0:
        return "Understand", 0.3
    return best, scores[best] / total


def level_index(level: str) -> int:
    return BLOOM_LEVELS.index(level)
