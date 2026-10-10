"""NOVEL COMPONENT 2 — Failure-memory guided regeneration.

Validators emit *typed failure codes* instead of a bare score. The memory
  - turns a slot's own failures into targeted repair constraints (local learning), and
  - promotes failure types that recur across the batch into *global* constraints
    injected pre-emptively into every future generation prompt (cross-question learning).
So the system makes a given mistake fewer times as the batch proceeds.
"""
from collections import Counter, deque

REPAIRS = {
    "OFF_TOPIC":           "Stay strictly on the target concept; mention it explicitly in the question.",
    "NOT_ANSWERABLE":      "The answer must be fully derivable from the source material; do not require outside knowledge.",
    "UNGROUNDED":          "Copy the evidence VERBATIM from the source material; never paraphrase it.",
    "BLOOM_MISMATCH":      "Start the question with a verb from the target Bloom level and match its cognitive demand.",
    "DIFFICULTY_MISMATCH": "Adjust complexity toward the target difficulty (scope, steps, concepts involved).",
    "GRAMMAR":             "Write one grammatical, unambiguous sentence ending in '?' or '.'.",
    "REDUNDANT":           "Ask about a different aspect or source sentence than existing questions.",
}


class FailureMemory:
    def __init__(self, window=20, promote_rate=0.25, min_count=2):
        self.recent = deque(maxlen=window)
        self.totals = Counter()
        self.promote_rate, self.min_count = promote_rate, min_count

    def record(self, codes):
        self.recent.append(tuple(codes))
        self.totals.update(codes)

    def global_codes(self):
        if not self.recent:
            return []
        c = Counter(code for att in self.recent for code in att)
        n = len(self.recent)
        return [k for k, v in c.items() if v >= self.min_count and v / n >= self.promote_rate]

    def constraints(self, local_codes):
        codes = list(dict.fromkeys(list(local_codes) + self.global_codes()))
        return [REPAIRS[c] for c in codes if c in REPAIRS]
