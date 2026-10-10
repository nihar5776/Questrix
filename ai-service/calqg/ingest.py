"""Stage 1: document processing, semantic chunking and curriculum/concept mapping."""
import re
from pathlib import Path

HEADING = re.compile(r"^(#{1,3})\s+(.*)$")


def load_text(path: str) -> str:
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(p) as pdf:
                return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        except ImportError:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
    return p.read_text(encoding="utf-8")


def clean(text: str) -> str:
    text = re.sub(r"-\n(\w)", r"\1", text)          # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def semantic_chunks(text: str, max_chars=700, overlap=100):
    """Chunk along the chapter -> topic hierarchy (markdown-style headings),
    then pack whole sentences so no chunk breaks mid-sentence."""
    chapter, topic, buf, chunks = "General", "General", [], []

    def flush():
        body = " ".join(buf).strip()
        if not body:
            return
        sents, cur = split_sentences(body), ""
        for s in sents:
            if len(cur) + len(s) > max_chars and cur:
                chunks.append((chapter, topic, cur.strip()))
                cur = cur[-overlap:] if overlap else ""
            cur += " " + s
        if cur.strip():
            chunks.append((chapter, topic, cur.strip()))

    for line in text.splitlines():
        m = HEADING.match(line.strip())
        if m:
            flush(); buf = []
            if len(m.group(1)) == 1:
                chapter = topic = m.group(2).strip()
            else:
                topic = m.group(2).strip()
        else:
            buf.append(line)
    flush()
    return chunks


def extract_concepts(text: str, vocab):
    """Whole-word match, longest concept first, so 'abstract class' is not also counted as 'class'."""
    low, found = text.lower(), set()
    for c in sorted(vocab, key=len, reverse=True):
        pat = r"\b" + re.escape(c.lower()) + r"s?\b"
        if re.search(pat, low):
            found.add(c)
            low = re.sub(pat, " ", low)
    return sorted(found)


def build_chunks(path: str, concept_vocab, cfg):
    text = clean(load_text(path))
    out = []
    for i, (ch, tp, body) in enumerate(semantic_chunks(text, cfg.chunk_size, cfg.chunk_overlap)):
        out.append({"id": f"c{i}", "text": body,
                    "meta": {"chapter": ch, "topic": tp, "source": Path(path).name,
                             "concepts": extract_concepts(body, concept_vocab)}})
    return out
