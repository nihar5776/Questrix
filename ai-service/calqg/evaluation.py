"""Stage 6 — evaluation & analysis: automatic metrics, human-vs-automatic agreement, ablation."""
import csv, statistics
import numpy as np
from scipy.stats import pearsonr, spearmanr, wilcoxon
from sklearn.metrics import cohen_kappa_score
from .config import Config

AUTO_KEYS = ["relevance", "answerability", "grounding", "bloom", "difficulty", "grammar", "redundancy"]


def auto_summary(questions):
    if not questions:
        return {}
    out = {k: round(statistics.mean(q["validation"][k]["score"] for q in questions), 3) for k in AUTO_KEYS}
    out["overall_quality"] = round(statistics.mean(q["quality_score"] for q in questions), 3)
    out["mean_attempts"] = round(statistics.mean(q["attempts"] for q in questions), 2)
    return out


def export_for_human_rating(questions, path):
    """CSV for college teachers / subject experts to rate on a 1-5 Likert scale."""
    cols = ["id", "question", "answer", "bloom_level", "difficulty", "source_snippet",
            "relevance", "answerability", "usefulness", "grammaticality", "bloom_alignment", "overall"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for i, q in enumerate(questions):
            w.writerow({"id": i, **{k: q.get(k, "") for k in cols[1:6]}})
    return path


def human_agreement(questions, ratings_csv, accept_at=4):
    """Agreement between automatic accept/reject and expert judgement (overall >= accept_at)."""
    rows = {int(r["id"]): r for r in csv.DictReader(open(ratings_csv, encoding="utf-8")) if r["overall"]}
    ids = sorted(rows)
    auto = [1 if questions[i]["quality_score"] >= Config().quality_threshold else 0 for i in ids]
    human = [1 if int(rows[i]["overall"]) >= accept_at else 0 for i in ids]
    auto_q = [questions[i]["quality_score"] for i in ids]
    human_q = [int(rows[i]["overall"]) for i in ids]
    res = {"n": len(ids), "cohen_kappa": round(cohen_kappa_score(auto, human), 3),
           "spearman_quality": round(spearmanr(auto_q, human_q)[0], 3)}
    for k in ["relevance", "answerability", "grammaticality"]:
        a = [questions[i]["validation"][{"grammaticality": "grammar"}.get(k, k)]["score"] for i in ids]
        h = [int(rows[i][k]) for i in ids if rows[i][k]]
        if len(h) == len(a) and len(set(h)) > 1:
            res[f"pearson_{k}"] = round(pearsonr(a, h)[0], 3)
    return res


def ablation(build_system, profile, variants, runs=5, batches=2):
    """build_system(**variant_kwargs) -> fresh CALQG. Each run generates `batches` consecutive
    batches (as a teacher would across weeks), repeated over several seeds."""
    table = {}
    for name, kw in variants.items():
        acc, att, cov, ungr = [], [], [], []
        for seed in range(runs):
            sys_ = build_system(**dict(kw))
            A, n, calls = [], 0, 0
            for b in range(batches):
                r = sys_.generate(dict(profile, seed=seed * 10 + b))
                A += r["accepted"]; n += len(r["accepted"]) + len(r["rejected"]); calls += len(r["trace"])
            acc.append(len(A) / n)
            att.append(calls / n)
            cov.append(len({q["concept"] for q in A}))
            bad = [q for q in A if not q["validation"]["grounding"].get("audit_passed",
                                                                          q["validation"]["grounding"]["passed"])]
            ungr.append(len(bad) / max(1, len(A)))
        table[name] = {"acceptance_rate": acc, "llm_calls_per_question": att,
                       "concepts_covered": cov, "ungrounded_accepted": ungr}
    return table


def compare(table, base, other, metric):
    """Paired Wilcoxon signed-rank test across seeds."""
    a, b = table[base][metric], table[other][metric]
    try:
        p = wilcoxon(a, b).pvalue if any(x != y for x, y in zip(a, b)) else 1.0
    except ValueError:
        p = float("nan")
    return round(float(np.mean(a)), 3), round(float(np.mean(b)), 3), round(float(p), 4)
