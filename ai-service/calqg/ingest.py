"""Stage 1: Document processing, PDF page extraction, semantic chunking, and concept mapping."""
import re
import hashlib
from pathlib import Path

HEADING = re.compile(r"^(#{1,3})\s+(.*)$")


def load_pdf_pages(path: str, progress_cb=None):
    """Extract text page by page from PDF files using pypdf (fast/lightweight) 
    with pdfplumber fallback. Preserves page numbers and checks for scanned PDFs."""
    p = Path(path)
    pages_data = []  # list of (page_num, text)
    
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError, FileNotDecryptedError
        
        try:
            reader = PdfReader(str(p))
            if reader.is_encrypted:
                try:
                    reader.decrypt('')
                except Exception:
                    raise ValueError("PDF file is password-protected or encrypted.")

            total_pages = len(reader.pages)
            for idx, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                pages_data.append((idx, page_text))
                if progress_cb and total_pages > 0 and (idx % 10 == 0 or idx == total_pages):
                    pct = 10.0 + (idx / total_pages) * 40.0
                    progress_cb(pct, f"Extracting PDF text (page {idx}/{total_pages})")

        except (PdfReadError, FileNotDecryptedError) as e:
            raise ValueError(f"PDF file is corrupted or unreadable: {str(e)}")
        except ValueError:
            raise
        except Exception:
            # Fallback to pdfplumber if pypdf hits an unexpected structure
            pages_data = []
            import pdfplumber
            with pdfplumber.open(p) as pdf:
                total_pages = len(pdf.pages)
                for idx, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    pages_data.append((idx, page_text))
                    if progress_cb and total_pages > 0 and (idx % 10 == 0 or idx == total_pages):
                        pct = 10.0 + (idx / total_pages) * 40.0
                        progress_cb(pct, f"Extracting PDF text via pdfplumber (page {idx}/{total_pages})")

    except ImportError:
        import pdfplumber
        with pdfplumber.open(p) as pdf:
            total_pages = len(pdf.pages)
            for idx, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                pages_data.append((idx, page_text))
                if progress_cb and total_pages > 0:
                    pct = 10.0 + (idx / total_pages) * 40.0
                    progress_cb(pct, f"Extracting PDF text (page {idx}/{total_pages})")

    # Validate extracted text to detect scanned PDFs or empty documents
    total_chars = sum(len(txt.strip()) for _, txt in pages_data)
    total_pages = len(pages_data)
    
    if total_chars < 50 or (total_pages > 3 and (total_chars / total_pages) < 10):
        raise ValueError(
            "Scanned or image-only PDF detected (no extractable text found). "
            "OCR processing is required for scanned documents."
        )

    return pages_data


def load_text(path: str, progress_cb=None):
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return load_pdf_pages(str(p), progress_cb)
    
    # Text or Markdown file
    raw_text = p.read_text(encoding="utf-8", errors="replace")
    if not raw_text.strip():
        raise ValueError("Uploaded text file is empty.")
    return [(1, raw_text)]


def clean(text: str) -> str:
    text = re.sub(r"-\n(\w)", r"\1", text)  # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]


def semantic_chunks_from_pages(pages_data, max_chars=700, overlap=100, progress_cb=None):
    """Chunk along headings and page boundaries while packing whole sentences."""
    chapter, topic, buf, chunks = "General", "General", [], []
    current_page = 1
    total_items = len(pages_data)

    def flush(pg_num):
        nonlocal buf
        body = clean(" ".join(buf))
        buf = []
        if not body:
            return
        sents, cur = split_sentences(body), ""
        for s in sents:
            if len(cur) + len(s) > max_chars and cur:
                chunks.append((pg_num, chapter, topic, cur.strip()))
                cur = cur[-overlap:] if overlap else ""
            cur += " " + s
        if cur.strip():
            chunks.append((pg_num, chapter, topic, cur.strip()))

    for idx, (pg_num, pg_text) in enumerate(pages_data, 1):
        current_page = pg_num
        for line in pg_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            m = HEADING.match(line_str)
            if m:
                flush(current_page)
                if len(m.group(1)) == 1:
                    chapter = topic = m.group(2).strip()
                else:
                    topic = m.group(2).strip()
            else:
                buf.append(line_str)

        # Flush at page boundary if buffer gets large (> 2000 chars)
        if sum(len(x) for x in buf) > 2000:
            flush(current_page)

        if progress_cb and total_items > 0 and idx % 20 == 0:
            pct = 50.0 + (idx / total_items) * 20.0
            progress_cb(pct, f"Structuring semantic chunks (page {idx}/{total_items})")

    flush(current_page)
    return chunks


def extract_concepts(text: str, vocab):
    """Whole-word match, longest concept first."""
    if not vocab:
        return []
    low, found = text.lower(), set()
    for c in sorted(vocab, key=len, reverse=True):
        pat = r"\b" + re.escape(c.lower()) + r"s?\b"
        if re.search(pat, low):
            found.add(c)
            low = re.sub(pat, " ", low)
    return sorted(found)


def compute_chunk_hash(text: str) -> str:
    return hashlib.md5(text.strip().encode("utf-8")).hexdigest()[:12]


def build_chunks(path: str, concept_vocab, cfg, progress_cb=None):
    if progress_cb:
        progress_cb(5.0, "Reading document file...")

    pages_data = load_text(path, progress_cb)
    
    if progress_cb:
        progress_cb(50.0, f"Generating chunks from {len(pages_data)} page(s)...")

    raw_chunks = semantic_chunks_from_pages(
        pages_data, 
        max_chars=getattr(cfg, 'chunk_size', 700), 
        overlap=getattr(cfg, 'chunk_overlap', 100),
        progress_cb=progress_cb
    )

    if not raw_chunks:
        raise ValueError("No valid text chunks could be generated from the document.")

    source_filename = Path(path).name
    out = []
    seen_hashes = set()

    for i, (pg_num, ch, tp, body) in enumerate(raw_chunks):
        h = compute_chunk_hash(body)
        if h in seen_hashes:
            continue  # Skip exact duplicate chunks
        seen_hashes.add(h)

        out.append({
            "id": f"c{i}_{h}",
            "text": body,
            "meta": {
                "page": pg_num,
                "chapter": ch,
                "topic": tp,
                "source": source_filename,
                "concepts": extract_concepts(body, concept_vocab)
            }
        })

    if progress_cb:
        progress_cb(70.0, f"Created {len(out)} unique semantic chunks.")

    return out
