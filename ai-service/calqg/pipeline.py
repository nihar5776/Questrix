"""LangGraph orchestration of the full plan -> retrieve -> generate -> repair -> validate loop."""
from collections import Counter
from typing import Any, TypedDict
from langgraph.graph import StateGraph, END

from .config import Config
from .embeddings import Embedder
from .vectorstore import VectorStore
from .ingest import build_chunks
from .llm import make_llm
from .irt import DifficultyModel
from .failure_memory import FailureMemory
from . import agents, validators


class QGState(TypedDict, total=False):
    profile: dict
    slots: list
    idx: int
    ctx: list
    candidate: dict
    attempt: int
    local_codes: list
    last_eval: dict
    accepted: list
    rejected: list
    trace: list


class CALQG:
    def __init__(self, cfg: Config = None, disabled_validators=()):
        self.cfg = cfg or Config()
        self.emb = Embedder()
        self.store = VectorStore(self.emb)
        self.llm = make_llm(self.cfg.llm_provider, self.cfg)
        self.dmodel = DifficultyModel(self.emb)
        self.memory = FailureMemory()
        self.bank = []                      # accepted questions persist across batches
        self.concept_stats = Counter()
        self.disabled = tuple(disabled_validators)
        self.graph = self._build_graph()

    # ---------- Stage 1: knowledge preparation ----------
    def ingest(self, path, concept_vocab, progress_cb=None):
        chunks = build_chunks(path, concept_vocab, self.cfg, progress_cb=progress_cb)
        self.store.add(chunks, progress_cb=progress_cb)
        for c in chunks:
            self.concept_stats.update(c["meta"]["concepts"])
        return len(chunks)

    # ---------- graph nodes ----------
    def _plan(self, s):
        slots = agents.planner_agent(s["profile"], self.concept_stats, self.bank, self.cfg)
        return {"slots": slots, "idx": 0, "accepted": [], "rejected": [], "trace": []}

    def _retrieve(self, s):
        slot = s["slots"][s["idx"]]
        return {"ctx": agents.retriever_agent(self.store, slot, self.cfg), "attempt": 0, "local_codes": []}

    def _generate(self, s):
        slot = s["slots"][s["idx"]]
        cons = self.memory.constraints(s["local_codes"]) if self.cfg.use_failure_memory else []
        q = agents.generator_agent(self.llm, slot, s["ctx"], cons, s["attempt"])
        q["_constraints_used"] = cons
        return {"candidate": q}

    def _repair(self, s):
        slot, q = s["slots"][s["idx"]], dict(s["candidate"])
        q = agents.bloom_agent(q, slot)
        q = agents.difficulty_agent(q, self.dmodel)
        q = agents.fact_check_agent(q, s["ctx"])
        q = agents.diversity_agent(q, slot, self.bank, self.emb, self.cfg.redundancy_threshold)
        return {"candidate": q}

    def _validate(self, s):
        slot, q = s["slots"][s["idx"]], s["candidate"]
        res, quality, passed, codes = validators.run_all(q, slot, s["ctx"], self.emb, self.dmodel,
                                                         self.bank, self.cfg, self.disabled)
        self.memory.record(codes)
        trace = s["trace"] + [{"slot": slot["slot_id"], "attempt": s["attempt"], "quality": quality,
                               "passed": passed, "codes": codes,
                               "n_constraints": len(q["_constraints_used"])}]
        return {"last_eval": {"results": res, "quality": quality, "passed": passed, "codes": codes},
                "trace": trace}

    def _route(self, s):
        if s["last_eval"]["passed"]:
            return "accept"
        return "regenerate" if s["attempt"] + 1 < self.cfg.max_attempts else "reject"

    def _regenerate(self, s):
        # Regeneration agent: carries this slot's failure codes into the next prompt
        codes = s["last_eval"]["codes"] if self.cfg.use_failure_memory else []
        return {"attempt": s["attempt"] + 1, "local_codes": list(dict.fromkeys(s["local_codes"] + codes))}

    def _finalise(self, s, ok):
        slot, q, ev = s["slots"][s["idx"]], dict(s["candidate"]), s["last_eval"]
        q.pop("_constraints_used", None)
        out = {"question": q["question"], "answer": q["answer"], "bloom_level": slot["bloom"],
               "difficulty": q.get("difficulty"), "difficulty_score": q.get("difficulty_score"),
               "source_snippet": q["evidence"], "source_refs": q["source_refs"],
               "topic": q["source_refs"][0]["topic"] if q["source_refs"] else None,
               "concept": slot["concept"], "question_type": slot["qtype"],
               "quality_score": ev["quality"], "attempts": s["attempt"] + 1,
               "validation": ev["results"], "evidence": q["evidence"], "concepts": q.get("concepts")}
        if ok:
            self.bank.append(out)
            return {"accepted": s["accepted"] + [out], "idx": s["idx"] + 1}
        return {"rejected": s["rejected"] + [out], "idx": s["idx"] + 1}

    def _more(self, s):
        return "next" if s["idx"] < len(s["slots"]) else "done"

    def _build_graph(self):
        g = StateGraph(QGState)
        g.add_node("plan", self._plan)
        g.add_node("retrieve", self._retrieve)
        g.add_node("generate", self._generate)
        g.add_node("repair", self._repair)
        g.add_node("validate", self._validate)
        g.add_node("regenerate", self._regenerate)
        g.add_node("accept", lambda s: self._finalise(s, True))
        g.add_node("reject", lambda s: self._finalise(s, False))
        g.set_entry_point("plan")
        g.add_conditional_edges("plan", self._more, {"next": "retrieve", "done": END})
        g.add_edge("retrieve", "generate")
        g.add_edge("generate", "repair")
        g.add_edge("repair", "validate")
        g.add_conditional_edges("validate", self._route,
                                {"accept": "accept", "regenerate": "regenerate", "reject": "reject"})
        g.add_edge("regenerate", "generate")
        for n in ("accept", "reject"):
            g.add_conditional_edges(n, self._more, {"next": "retrieve", "done": END})
        return g.compile()

    def generate(self, profile):
        out = self.graph.invoke({"profile": profile}, config={"recursion_limit": 1000})
        return {"accepted": out["accepted"], "rejected": out["rejected"], "trace": out["trace"]}
