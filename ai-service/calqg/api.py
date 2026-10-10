"""REST API consumed by the Node.js/Express backend.
Run:  uvicorn calqg.api:app --port 8000"""
import os, shutil, tempfile
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from .pipeline import CALQG
from .evaluation import auto_summary

app = FastAPI(title="CAL-QG AI Service")
SYSTEM = CALQG()


class Profile(BaseModel):
    subject: str = "Java"
    num_questions: int = 6
    concepts: list[str] | None = None
    bloom_levels: list[str] | None = None
    difficulty: str | None = None            # Easy | Medium | Hard (else derived from Bloom)
    question_type: str = "Descriptive"
    seed: int = 0


class Calibration(BaseModel):
    question_ids: list[int]                  # indices into the accepted bank (column order)
    responses: list[list[float | None]]      # students x items, 1 correct / 0 wrong / null unanswered


@app.get("/health")
def health():
    return {"llm": SYSTEM.llm.name, "embedder": SYSTEM.emb.kind, "chunks": len(SYSTEM.store.chunks),
            "bank_size": len(SYSTEM.bank), "difficulty_calibrated": SYSTEM.dmodel.calibrated}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...), concepts: str = Form(...)):
    """concepts: newline- or comma-separated concept vocabulary for the syllabus unit."""
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
    vocab = [c.strip() for c in concepts.replace(",", "\n").splitlines() if c.strip()]
    n = SYSTEM.ingest(tmp.name, vocab)
    os.unlink(tmp.name)
    return {"chunks_added": n, "concepts": dict(SYSTEM.concept_stats)}


@app.post("/generate")
def generate(p: Profile):
    r = SYSTEM.generate(p.model_dump())
    return {"questions": r["accepted"], "rejected": r["rejected"],
            "summary": auto_summary(r["accepted"]), "trace": r["trace"]}


@app.post("/calibrate")
def calibrate(c: Calibration):
    items = [SYSTEM.bank[i] for i in c.question_ids]
    resp = [[float("nan") if v is None else v for v in row] for row in c.responses]
    b = SYSTEM.dmodel.calibrate(items, resp)
    return {"item_difficulty_logits": [round(float(x), 3) for x in b]}
