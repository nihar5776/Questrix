"""REST API consumed by the Node.js/Express backend with Background Job Processing."""
import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel
from .pipeline import CALQG
from .evaluation import auto_summary
from . import jobs

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
    active_job = jobs.get_active_job()
    return {
        "llm": SYSTEM.llm.name,
        "embedder": SYSTEM.emb.kind,
        "chunks": len(SYSTEM.store.chunks),
        "bank_size": len(SYSTEM.bank),
        "difficulty_calibrated": SYSTEM.dmodel.calibrated,
        "active_job": active_job
    }


@app.post("/ingest")
async def ingest_async(file: UploadFile = File(...), concepts: str = Form(...)):
    """Asynchronous Document Ingestion: Saves upload, starts background job, returns job_id immediately."""
    filename = file.filename or "uploaded_document.pdf"
    suffix = os.path.splitext(filename)[1] or ".pdf"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    filesize = os.path.getsize(tmp_path)
    vocab = [c.strip() for c in concepts.replace(",", "\n").splitlines() if c.strip()]
    
    job_data = jobs.create_job(
        temp_file_path=tmp_path,
        filename=filename,
        filesize=filesize,
        concept_vocab=vocab,
        pipeline_instance=SYSTEM
    )

    return {
        "job_id": job_data["job_id"],
        "status": job_data["status"],
        "message": f"Ingestion job queued for {filename}",
        "filename": filename,
        "filesize": filesize
    }


@app.get("/ingest/job/{job_id}")
def get_job_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job {job_id} not found.")
    return job


@app.get("/ingest/status")
def get_latest_status():
    active_job = jobs.get_active_job()
    return {
        "total_chunks": len(SYSTEM.store.chunks),
        "latest_job": active_job
    }


@app.post("/ingest/sync")
async def ingest_sync(file: UploadFile = File(...), concepts: str = Form(...)):
    """Synchronous fallback for small documents."""
    suffix = os.path.splitext(file.filename)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        vocab = [c.strip() for c in concepts.replace(",", "\n").splitlines() if c.strip()]
        n = SYSTEM.ingest(tmp_path, vocab)
        return {"chunks_added": n, "concepts": dict(SYSTEM.concept_stats)}
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/generate")
def generate(p: Profile):
    if len(SYSTEM.store.chunks) == 0:
        raise HTTPException(
            status_code=400,
            detail="No document ingested. Please ingest a syllabus or textbook before generating questions."
        )
    r = SYSTEM.generate(p.model_dump())
    return {
        "questions": r["accepted"],
        "rejected": r["rejected"],
        "summary": auto_summary(r["accepted"]),
        "trace": r["trace"]
    }


@app.post("/calibrate")
def calibrate(c: Calibration):
    items = [SYSTEM.bank[i] for i in c.question_ids]
    resp = [[float("nan") if v is None else v for v in row] for row in c.responses]
    b = SYSTEM.dmodel.calibrate(items, resp)
    return {"item_difficulty_logits": [round(float(x), 3) for x in b]}
