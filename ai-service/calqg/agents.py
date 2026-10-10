"""Stage 3 — specialised agents. Design principle: agents GENERATE and REPAIR; validators only JUDGE."""
import numpy as np
from collections import Counter
from .config import BLOOM_LEVELS
from .bloom import classify
from .ingest import split_sentences
from .textutil import span_ratio
from .embeddings import cosine

DEFAULT_BLOOM_MIX = {"Remember": .15, "Understand": .25, "Apply": .2, "Analyze": .2, "Evaluate": .1, "Create": .1}
BLOOM_TO_DIFF = {"Remember": "Easy", "Understand": "Easy", "Apply": "Medium",
                 "Analyze": "Hard", "Evaluate": "Hard", "Create": "Hard"}


def planner_agent(profile, concept_stats, bank, cfg):
    """Coverage-aware planner: allocates Bloom levels to hit a target distribution and
    concepts by *coverage deficit* = importance (corpus frequency) / (1 + times already asked)."""
    n = profile.get("num_questions", 6)
    levels = profile.get("bloom_levels") or BLOOM_LEVELS
    mix = {l: DEFAULT_BLOOM_MIX[l] for l in levels}
    tot = sum(mix.values()); mix = {k: v / tot for k, v in mix.items()}
    # largest-remainder allocation of n questions over Bloom levels
    raw = {k: v * n for k, v in mix.items()}
    alloc = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - alloc[k], reverse=True)[: n - sum(alloc.values())]:
        alloc[k] += 1
    blooms = [l for l in levels for _ in range(alloc[l])]

    concepts = profile.get("concepts") or list(concept_stats) or ["General"]
    asked = Counter(q["concept"] for q in bank)
    slots = []
    for i, b in enumerate(blooms):
        if cfg.use_coverage_planner:
            # least-covered concept first; corpus importance breaks ties
            c = min(concepts, key=lambda c: (asked[c], -concept_stats.get(c, 0)))
        else:
            c = concepts[i % len(concepts)]
        asked[c] += 1
        diff = profile.get("difficulty") or BLOOM_TO_DIFF[b]
        slots.append({"slot_id": i, "concept": c, "bloom": b, "difficulty_label": diff,
                      "qtype": profile.get("question_type", "Descriptive"),
                      "subject": profile.get("subject", "Java"), "avoid_evidence": [], "seed": profile.get("seed", 0) * 100 + i})
    return slots


def retriever_agent(store, slot, cfg, lam=0.7):
    """RAG retrieval with Maximal Marginal Relevance so the context is relevant AND non-redundant."""
    cands = store.search(f"{slot['concept']} {slot['bloom']}", k=cfg.top_k * 3)
    if not cands:
        return []
    V = store.emb.encode([c["text"] for c in cands])
    chosen = [0]
    while len(chosen) < min(cfg.top_k, len(cands)):
        best, best_s = None, -1e9
        for i in range(len(cands)):
            if i in chosen: continue
            s = lam * cands[i]["score"] - (1 - lam) * max(cosine(V[i], V[j]) for j in chosen)
            if s > best_s: best, best_s = i, s
        chosen.append(best)
    ctx = [cands[i] for i in chosen]
    # related concepts: prefer those in the same chapter as the best-matching chunk
    home = next((x["meta"]["chapter"] for x in ctx if slot["concept"] in x["meta"]["concepts"]),
                ctx[0]["meta"]["chapter"])
    rel = Counter(c for x in ctx for c in x["meta"]["concepts"] if c != slot["concept"])
    slot["related"] = sorted(rel, key=lambda c: (-any(c in x["meta"]["concepts"] and
                             x["meta"]["chapter"] == home for x in ctx), -rel[c]))[:3]
    return ctx


def generator_agent(llm, slot, ctx, constraints, attempt):
    q = llm.generate_question(slot, ctx, constraints, attempt)
    q.setdefault("concept", slot["concept"]); q.setdefault("bloom", slot["bloom"])
    q["concepts"] = sorted({slot["concept"], *[c for c in slot.get("related", []) if c.lower() in q["question"].lower()]})
    q["source_refs"] = [{"chunk": c["id"], "chapter": c["meta"]["chapter"], "topic": c["meta"]["topic"]} for c in ctx]
    return q


def bloom_agent(q, slot):
    lvl, conf = classify(q["question"])
    q["bloom_detected"], q["bloom_confidence"] = lvl, round(conf, 2)
    return q


def difficulty_agent(q, dmodel):
    u = dmodel.to_unit(dmodel.predict_b(q))
    q["difficulty_score"], q["difficulty"] = round(u, 3), dmodel.label(u)
    return q


def fact_check_agent(q, ctx, snap=0.97):
    """Repairs trivial evidence drift (whitespace/punctuation) by snapping to the exact source
    sentence. Real paraphrase is NOT repaired — it is left for the grounding validator to reject."""
    src = [s for c in ctx for s in split_sentences(c["text"])]
    fixed = []
    for e in split_sentences(q.get("evidence", "")) or [q.get("evidence", "")]:
        best = max(src, key=lambda s: span_ratio(e, s), default=e)
        fixed.append(best if span_ratio(e, best) >= snap else e)
    q["evidence"] = " ".join(fixed)
    return q


def diversity_agent(q, slot, bank, emb, thr):
    """Early duplicate detection: blocks the reused source sentence for the next attempt."""
    if not bank:
        return q
    qv = emb.encode(q["question"])[0]
    if any(b["evidence"] == q["evidence"] or cosine(qv, emb.encode(b["question"])[0]) >= thr for b in bank):
        slot["avoid_evidence"].extend(split_sentences(q["evidence"]))
    return q
