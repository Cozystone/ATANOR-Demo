# -*- coding: utf-8 -*-
"""Book ingestion — feed ATANOR a PDF and let it READ, like a person.

Owner's vision (2026-07-09): once the engine is mature enough, you should be
able to hand it a book or document and it reads on its own — 'Thinking, Fast
and Slow' so it learns about thinking about thinking. Human-like learning: not
only Wikidata dumps, but real books.

This is the front door. A PDF becomes sentences, sentences enter the SAME
learning pipeline as the web firehose (relation checking behind the consensus /
quality gate), so nothing bypasses the truth gates — a book is a high-quality
CORPUS, not an override. Two extraction paths, auto-selected per page:
  * TEXT layer (fitz/PyMuPDF) for born-digital PDFs — fast, exact;
  * OCR (pytesseract on a rendered page image) for scanned pages with no text
    layer — so a photographed book still reads.

The output is a corpus .txt in the firehose's corpus dir; the running learner
picks it up. Honest scope: today's relation extraction is co-occurrence-level
(gated), so a book surfaces its CONCEPTS and their associations as candidates —
the deep argument structure needs richer extraction (a named next step)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SENT_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n{2,}")


@dataclass
class IngestResult:
    source: str
    pages: int
    pages_ocr: int
    sentences: int
    corpus_file: str
    chars: int
    ocr_available: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "pages": self.pages, "pages_ocr": self.pages_ocr,
                "sentences": self.sentences, "corpus_file": self.corpus_file,
                "chars": self.chars, "ocr_available": self.ocr_available, "note": self.note}


def _ocr_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_pdf_text(path: str | Path, *, ocr_scanned: bool = True,
                     max_pages: int | None = None,
                     log: Any = print) -> tuple[str, int, int]:
    """Extract text from a PDF. Per page: use the text layer; if it's empty
    (scanned) and OCR is available, render the page and OCR it. Returns
    (text, pages_read, pages_ocr)."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    n = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
    have_ocr = ocr_scanned and _ocr_available()
    parts: list[str] = []
    pages_ocr = 0
    for i in range(n):
        page = doc.load_page(i)
        txt = page.get_text("text").strip()
        if len(txt) < 40 and have_ocr:            # likely a scanned/image page
            try:
                import io

                import pytesseract
                from PIL import Image
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                txt = pytesseract.image_to_string(img).strip()
                pages_ocr += 1
            except Exception:
                pass
        if txt:
            parts.append(txt)
        if i and i % 25 == 0:
            log(f"  ...{i}/{n} pages")
    doc.close()
    return "\n\n".join(parts), n, pages_ocr


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for chunk in _SENT_SPLIT.split(text):
        s = re.sub(r"\s+", " ", chunk).strip()
        # keep real sentences: length-bounded, has letters, not a page header/number
        if 20 <= len(s) <= 600 and re.search(r"[A-Za-z가-힣]", s) and not s.isupper():
            out.append(s)
    return out


def ingest_book(path: str | Path, *, corpus_dir: str | Path | None = None,
                title: str | None = None, ocr_scanned: bool = True,
                max_pages: int | None = None, log: Any = print) -> IngestResult:
    """Read a PDF into the firehose corpus so the running learner ingests it
    behind the same truth gates. Returns stats. Does NOT bypass promotion —
    the book is a corpus, its facts still pass the consensus/quality gate."""
    path = Path(path)
    if not path.exists():
        return IngestResult(str(path), 0, 0, 0, "", 0, _ocr_available(),
                            note="file not found")
    if corpus_dir is None:
        corpus_dir = Path(__file__).resolve().parent / "seed_corpus"
    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    text, pages, pages_ocr = extract_pdf_text(
        path, ocr_scanned=ocr_scanned, max_pages=max_pages, log=log)
    sents = _sentences(text)
    slug = re.sub(r"[^\w가-힣]+", "_", (title or path.stem)).strip("_").lower()[:60]
    out = corpus_dir / f"book_{slug}.txt"
    out.write_text("\n".join(sents), encoding="utf-8")
    return IngestResult(
        source=str(path), pages=pages, pages_ocr=pages_ocr, sentences=len(sents),
        corpus_file=str(out), chars=len(text), ocr_available=_ocr_available(),
        note=("read via OCR on scanned pages" if pages_ocr else "read from text layer")
        + " — corpus written; the running learner ingests it behind the truth gates")
