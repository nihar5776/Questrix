"""Stage 4 — independent validators. Each returns score in [0,1], pass flag and a typed failure code.
NOVEL COMPONENT 1 — Evidence-anchored validation: answerability and grounding are checked
*deterministically* against the retrieved source spans, not by asking an LLM to grade itself."""
from .bloom import classify, level_index
from .ingest import split_sentences
from .textutil import token_recall, span_ratio
from .embeddings import cosine

TARGET_U = {"Easy": 0.30, "Medium": 0.55, "Hard": 0.80}


def _res(score, passed, code, msg):
    return {"score": round(max(0.0, min(1.0, score)), 3), "passed": bool(passed),
            "code": None if passed else code, "msg": msg}


def relevance(q, slot, ctx, emb):
    in_q = slot["concept"].lower() in q["question"].lower()
    qv = emb.encode(q["question"] + " " + q["answer"])[0]
    sim = max(cosine(qv, emb.encode(c["text"])[0]) for c in ctx)
    s = 0.5 * in_q + 0.5 * min(1.0, sim / 0.35)
    return _res(s, in_q and sim >= 0.10, "OFF_TOPIC", f"concept_in_question={in_q}, ctx_sim={sim:.2f}")


def answerability(q, slot, ctx, emb):
    ctx_text = " ".join(c["text"] for c in ctx)
    r = token_recall(q["answer"], ctx_text)
    return _res(r, r >= 0.80, "NOT_ANSWERABLE", f"answer content found in source: {r:.0%}")


def grounding(q, slot, ctx, emb):
    src = [s for c in ctx for s in split_sentences(c["text"])]
    ev = split_sentences(q.get("evidence", "")) or [q.get("evidence", "")]
    span = sum(max((span_ratio(e, s) for s in src), default=0) for e in ev) / len(ev)
    support = token_recall(q["answer"], q.get("evidence", ""))
    s = 0.6 * span + 0.4 * support
    return _res(s, span >= 0.98 and support >= 0.70, "UNGROUNDED",
                f"evidence verbatim-match={span:.2f}, answer supported by evidence={support:.0%}")


def bloom(q, slot, ctx, emb):
    lvl, conf = classify(q["question"])
    d = abs(level_index(lvl) - level_index(slot["bloom"]))
    return _res(1.0 if d == 0 else (0.5 if d == 1 else 0.0), d == 0, "BLOOM_MISMATCH",
                f"detected={lvl} (conf {conf:.2f}) target={slot['bloom']}")


def difficulty(q, slot, ctx, emb, dmodel):
    u = dmodel.to_unit(dmodel.predict_b(q))
    q["difficulty_score"], q["difficulty"] = round(u, 3), dmodel.label(u)
    gap = abs(u - TARGET_U[slot["difficulty_label"]])
    return _res(1 - gap / 0.5, gap <= 0.25, "DIFFICULTY_MISMATCH",
                f"predicted={u:.2f} ({q['difficulty']}) target={slot['difficulty_label']}")


def grammar(q, slot, ctx, emb):
    t, issues = q["question"].strip(), []
    if not t or not t[0].isupper(): issues.append("capitalisation")
    if t[-1:] not in "?.": issues.append("terminal punctuation")
    w = t.lower().split()
    if any(a == b for a, b in zip(w, w[1:])): issues.append("repeated word")
    if not 4 <= len(w) <= 60: issues.append("length")
    return _res(1 - 0.34 * len(issues), not issues, "GRAMMAR", ", ".join(issues) or "ok")


def redundancy(q, slot, ctx, emb, bank, thr):
    if not bank:
        return _res(1.0, True, "REDUNDANT", "first question")
    qv = emb.encode(q["question"])[0]
    sims = [cosine(qv, emb.encode(b["question"])[0]) for b in bank]
    same_ev = any(b["evidence"] == q["evidence"] for b in bank)
    m = max(sims)
    return _res(1 - max(0.0, m - 0.5) / 0.5, m < thr and not same_ev, "REDUNDANT",
                f"max similarity to bank={m:.2f}, same_evidence={same_ev}")


def run_all(q, slot, ctx, emb, dmodel, bank, cfg, disabled=()):
    res = {
        "relevance": relevance(q, slot, ctx, emb),
        "answerability": answerability(q, slot, ctx, emb),
        "grounding": grounding(q, slot, ctx, emb),
        "bloom": bloom(q, slot, ctx, emb),
        "difficulty": difficulty(q, slot, ctx, emb, dmodel),
        "grammar": grammar(q, slot, ctx, emb),
        "redundancy": redundancy(q, slot, ctx, emb, bank, cfg.redundancy_threshold),
    }
    for d in disabled:                      # ablation: treat a disabled validator as always passing
        raw = res[d]
        res[d] = _res(1.0, True, None, "disabled (ablation)")
        res[d]["audit_passed"] = raw["passed"]   # true outcome, kept for ablation reporting
    quality = sum(cfg.weights[k] * v["score"] for k, v in res.items())
    gates_ok = all(res[g]["passed"] for g in cfg.hard_gates)
    passed = quality >= cfg.quality_threshold and gates_ok
    codes = [v["code"] for v in res.values() if v["code"]]
    return res, round(quality, 3), passed, codes
