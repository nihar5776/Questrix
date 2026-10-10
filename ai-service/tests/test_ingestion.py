import os
import time
import pytest
from pathlib import Path
from calqg.config import Config
from calqg.pipeline import CALQG
from calqg import ingest, jobs

def test_load_text_markdown():
    path = "sample_data/java_oop_unit2.md"
    pages = ingest.load_text(path)
    assert len(pages) >= 1
    assert "Inheritance" in pages[0][1]

def test_build_chunks_and_deduplication():
    cfg = Config()
    vocab = ["Inheritance", "Polymorphism", "Encapsulation", "Class", "Object"]
    chunks = ingest.build_chunks("sample_data/java_oop_unit2.md", vocab, cfg)
    assert len(chunks) > 0
    assert "page" in chunks[0]["meta"]
    assert chunks[0]["meta"]["page"] == 1

def test_vectorstore_add_deduplication():
    s = CALQG(Config())
    vocab = ["Arrays", "Stacks", "Trees"]
    chunks = ingest.build_chunks("sample_data/data_structures_syllabus.md", vocab, s.cfg)
    s.store.add(chunks)
    initial_count = len(s.store.chunks)
    assert initial_count > 0
    # Re-adding same chunks should skip duplicates
    s.store.add(chunks)
    assert len(s.store.chunks) == initial_count

def test_async_job_manager():
    s = CALQG(Config())
    vocab = ["Inheritance", "Polymorphism"]
    job = jobs.create_job("sample_data/java_oop_unit2.md", "java_oop_unit2.md", 4500, vocab, s)
    assert job["status"] in ("queued", "processing", "completed")
    
    # Wait for background thread worker to finish
    max_wait = 10
    start = time.time()
    completed_job = None
    while time.time() - start < max_wait:
        j = jobs.get_job(job["job_id"])
        if j["status"] in ("completed", "failed"):
            completed_job = j
            break
        time.sleep(0.5)

    assert completed_job is not None
    assert completed_job["status"] == "completed"
    assert completed_job["chunks_added"] > 0
    assert completed_job["progress"] == 100.0

def test_scanned_pdf_detection(tmp_path):
    # Create an empty / blank text file mimicking scanned image PDF
    blank_pdf = tmp_path / "scanned_doc.pdf"
    blank_pdf.write_bytes(b"%PDF-1.4 blank content with no extractable text")
    with pytest.raises(ValueError) as exc_info:
        ingest.load_pdf_pages(str(blank_pdf))
    assert "Scanned or image-only PDF detected" in str(exc_info.value) or "corrupted" in str(exc_info.value)
