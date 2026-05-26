"""PDF search and redaction engine. No UI dependencies."""

import os
import re
from typing import cast
import fitz  # PyMuPDF


def _turkish_casefold(s: str) -> str:
    # Standard casefold mishandles İ/I/ı — all four map to 'i' here.
    return (
        s
        .replace('İ', 'i')
        .replace('I', 'i')
        .replace('ı', 'i')
        .lower()
    )


def _strip_word_punct(w: str) -> str:
    return re.sub(r'^[^\wÀ-ɏ]+|[^\wÀ-ɏ]+$', '', w)


def _search_page(
    page: fitz.Page,
    term: str,
    case_sensitive: bool,
    whole_word: bool,
) -> list[dict]:
    rects: list[fitz.Rect] = []

    if not case_sensitive and not whole_word:
        # PyMuPDF'in kendi araması: hızlı, case-insensitive, kısmi eşleşme
        rects = list(page.search_for(term))
    else:
        term_tokens = term.split()
        n = len(term_tokens)

        def tok_matches(raw_word: str, target: str) -> bool:
            w = _strip_word_punct(raw_word)
            if whole_word:
                if case_sensitive:
                    return w == target
                return _turkish_casefold(w) == _turkish_casefold(target)
            else:
                return target in w

        words_data = page.get_text("words")  # type: ignore[union-attr]
        lines: dict[tuple[int, int], list] = {}
        for w in words_data:
            k = (int(w[5]), int(w[6]))
            lines.setdefault(k, []).append(w)

        for line_words in lines.values():
            line_words.sort(key=lambda w: w[7])
            for i in range(len(line_words) - n + 1):
                if all(tok_matches(line_words[i + j][4], term_tokens[j]) for j in range(n)):
                    x0 = min(line_words[i + j][0] for j in range(n))
                    y0 = min(line_words[i + j][1] for j in range(n))
                    x1 = max(line_words[i + j][2] for j in range(n))
                    y1 = max(line_words[i + j][3] for j in range(n))
                    rects.append(fitz.Rect(x0, y0, x1, y1))

    results: list[dict] = []
    page_rect = page.rect
    for r in rects:
        ctx_rect = fitz.Rect(
            max(page_rect.x0, r.x0 - 200),
            r.y0 - 2,
            min(page_rect.x1, r.x1 + 200),
            r.y1 + 2
        )
        ctx_text = page.get_textbox(ctx_rect).replace('\n', ' ').strip()
        
        if len(ctx_text) > 90:
            idx = ctx_text.lower().find(term.lower())
            if idx != -1:
                start = max(0, idx - 40)
                end = min(len(ctx_text), idx + len(term) + 40)
                ctx_text = ("..." if start > 0 else "") + ctx_text[start:end] + ("..." if end < len(ctx_text) else "")
            else:
                ctx_text = ctx_text[:87] + "..."
                
        results.append({
            "rect": r,
            "context": ctx_text
        })

    return results


def search_all_pages(
    doc: fitz.Document,
    terms: list[str],
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> list[dict]:
    results = []
    for i in range(len(doc)):
        page = cast(fitz.Page, doc[i])
        hits = []
        for term in terms:
            term_hits = _search_page(page, term, case_sensitive, whole_word)
            for hit in term_hits:
                hit["matched_term"] = term
            hits.extend(term_hits)
            
        if hits:
            serialized_hits = []
            for hit in hits:
                r = hit["rect"]
                serialized_hits.append({
                    "rect": {"x": r.x0, "y": r.y0, "w": r.width, "h": r.height},
                    "context": hit["context"],
                    "matched_term": hit["matched_term"]
                })
            results.append({
                "page_index": i,
                "page_num":   i + 1,
                "matches":    serialized_hits,
                "count":      len(hits)
            })
    return results





def has_text_layer(doc: fitz.Document, sample_pages: int = 5) -> bool:
    pages_to_check = min(sample_pages, len(doc))
    for i in range(pages_to_check):
        text = cast(str, cast(fitz.Page, doc[i]).get_text()).strip()
        if len(text) > 20:
            return True
    return False


def clean_metadata(doc: fitz.Document) -> None:
    doc.set_metadata({
        "author": "", "producer": "", "creator": "",
        "title": "", "subject": "", "keywords": "",
        "creationDate": "", "modDate": "",
    })
    try:
        doc.del_xml_metadata()
    except Exception:
        pass


def save_pdf(doc: fitz.Document, output_path: str) -> None:
    # garbage=4 purges superseded xref objects — critical after redaction.
    doc.save(output_path, garbage=4, deflate=True, clean=True)


def open_pdf(path: str) -> fitz.Document:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Dosya bulunamadı: {path}")
    return fitz.open(path)


def redact_areas(doc: fitz.Document, page_index: int, rects: list) -> None:
    """Koordinat listesiyle alan sansürler."""
    page = cast(fitz.Page, doc[page_index])
    for rect in rects:
        page.add_redact_annot(fitz.Rect(rect), fill=(0, 0, 0))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)  # type: ignore[attr-defined]



