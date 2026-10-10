import numpy as np
from fastapi.testclient import TestClient
from calqg.bloom import classify
from calqg.irt import fit_rasch
from calqg.failure_memory import FailureMemory
from calqg.config import Config
from calqg.pipeline import CALQG

VOCAB = [v.strip() for v in open("sample_data/concepts_java.txt") if v.strip()]


def test_bloom():
    assert classify("Define inheritance.")[0] == "Remember"
    assert classify("Differentiate between overloading and overriding.")[0] == "Analyze"
    assert classify("Design a class hierarchy for a bank.")[0] == "Create"


def test_rasch_recovers_order():
    rng = np.random.default_rng(0)
    b = np.array([-2, -1, 0, 1, 2.0]); th = rng.normal(0, 1, 400)
    R = (rng.random((400, 5)) < 1 / (1 + np.exp(-(th[:, None] - b)))).astype(float)
    _, est = fit_rasch(R)
    assert list(np.argsort(est)) == [0, 1, 2, 3, 4]


def test_failure_memory_promotes_recurring_codes():
    m = FailureMemory(min_count=2, promote_rate=0.25)
    for _ in range(3): m.record(["UNGROUNDED"])
    m.record([])
    assert "UNGROUNDED" in m.global_codes()
    assert any("VERBATIM" in c for c in m.constraints([]))


def test_pipeline_outputs_grounded_questions():
    s = CALQG(Config()); s.ingest("sample_data/java_oop_unit2.md", VOCAB)
    r = s.generate({"num_questions": 6})
    assert r["accepted"]
    for q in r["accepted"]:
        assert q["validation"]["grounding"]["passed"]
        assert q["validation"]["bloom"]["passed"]
        assert {"question", "bloom_level", "difficulty", "source_snippet", "topic", "question_type"} <= q.keys()


def test_api():
    from calqg import api
    c = TestClient(api.app)
    with open("sample_data/java_oop_unit2.md", "rb") as f:
        assert c.post("/ingest", files={"file": ("u2.md", f)},
                      data={"concepts": "\n".join(VOCAB)}).status_code == 200
    r = c.post("/generate", json={"num_questions": 4}).json()
    assert len(r["questions"]) >= 1
    n = len(r["questions"])
    resp = np.random.default_rng(1).integers(0, 2, (30, n)).tolist()
    assert c.post("/calibrate", json={"question_ids": list(range(n)), "responses": resp}).status_code == 200
    assert c.get("/health").json()["difficulty_calibrated"]
