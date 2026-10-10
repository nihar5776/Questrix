"""Thread-safe background ingestion job manager for Questrix AI."""
import os
import uuid
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

logger = logging.getLogger("calqg.jobs")

_LOCK = Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_JOBS = {}


def create_job(temp_file_path: str, filename: str, filesize: int, concept_vocab: list, pipeline_instance) -> dict:
    job_id = str(uuid.uuid4())
    now = time.time()
    
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "stage": "Job queued",
        "filename": filename,
        "filesize": filesize,
        "chunks_added": 0,
        "concepts": {},
        "error": None,
        "created_at": now,
        "updated_at": now
    }

    with _LOCK:
        _JOBS[job_id] = job_data

    _EXECUTOR.submit(_run_ingestion_worker, job_id, temp_file_path, concept_vocab, pipeline_instance)
    return job_data


def get_job(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            return dict(job)
    return None


def get_all_jobs() -> list:
    with _LOCK:
        return [dict(j) for j in _JOBS.values()]


def get_active_job() -> dict | None:
    """Returns the most recent active or completed job."""
    with _LOCK:
        if not _JOBS:
            return None
        sorted_jobs = sorted(_JOBS.values(), key=lambda x: x["created_at"], reverse=True)
        return dict(sorted_jobs[0])


def _update_job(job_id: str, **kwargs):
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(kwargs)
            _JOBS[job_id]["updated_at"] = time.time()


def _run_ingestion_worker(job_id: str, temp_file_path: str, concept_vocab: list, pipeline):
    _update_job(job_id, status="processing", progress=5.0, stage="Starting document analysis...")

    def progress_callback(pct: float, stage_msg: str):
        _update_job(job_id, progress=round(float(pct), 1), stage=stage_msg)

    try:
        chunks_count = pipeline.ingest(temp_file_path, concept_vocab, progress_cb=progress_callback)
        _update_job(
            job_id,
            status="completed",
            progress=100.0,
            stage="Ingestion completed successfully",
            chunks_added=chunks_count,
            concepts=dict(pipeline.concept_stats),
            error=None
        )
        logger.info(f"Ingestion job {job_id} completed: {chunks_count} chunks from {pipeline.store.chunks[-1]['meta']['source'] if pipeline.store.chunks else 'file'}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ingestion job {job_id} failed: {error_msg}", exc_info=True)
        _update_job(
            job_id,
            status="failed",
            progress=0.0,
            stage="Ingestion failed",
            error=error_msg
        )

    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {cleanup_err}")
