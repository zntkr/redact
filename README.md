# redact

Desktop tool for permanently removing sensitive content from PDF files.

## Why this exists

Most "redaction" tools draw black rectangles over text. The underlying text remains in the file — anyone can select it, copy it, or extract it with a parser. redact uses PyMuPDF's redaction API to physically remove text characters and image pixels from the document at the byte level. It also strips all metadata (author, creation date, XMP, producer string) that could identify the source.

## Features

- **True redaction** — text is removed from the file, not just painted over
- **Metadata scrubbing** — author, title, dates, XMP data, producer string
- **Three redaction methods:**
  - Drag to select text → instant redact on mouse release
  - Draw mode — freehand rectangle over any area (images, diagrams, etc.)
  - Keyword search → inspect matches in context → cherry-pick → batch redact
- **Turkish character support** — `İ / I / ı / i` normalization for accurate case-insensitive search
- **Multi-term search** — comma or newline separated, searches all pages
- **Multi-tab** — work on several documents simultaneously
- **Undo / redo** — full history per tab (Ctrl+Z / Ctrl+Y)
- **Drag & drop** — drop a PDF directly onto the window
- **Scanned PDF detection** — warns when no text layer is present

## Stack

| Layer | Technology |
|---|---|
| PDF engine | [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) |
| Desktop bridge | [pywebview](https://pywebview.flowrl.com/) |
| PDF renderer | [PDF.js](https://mozilla.github.io/pdf.js/) (bundled, no CDN) |
| UI | Vanilla HTML / CSS / JS |

No Electron. No Node. The binary footprint is Python + two pip packages.

## Requirements

- Python 3.10+
- Windows, macOS, or Linux

## Installation

```bash
pip install pymupdf pywebview
python main.py
```

## How to use

1. Click **PDF Aç** or drop a PDF onto the window
2. **Select text** with your cursor — it is redacted immediately on mouse release
3. Switch to **Çiz** mode to draw rectangles over images or non-selectable areas
4. Use the **search box** to find terms across all pages — check individual matches to stage them for redaction automatically
5. Click **Tüm Değişiklikleri Kaydet** — a save dialog appears, the redacted copy is written, and the original is untouched

Right-click a pending redaction rectangle to remove it. Ctrl+Z undoes the last action.

## How redaction works

```
Mark areas  →  add_redact_annot()  →  apply_redactions()  →  save(garbage=4)
```

`apply_redactions()` removes the text characters and repaints the pixels. `garbage=4` on save purges superseded cross-reference objects so previous revisions of the page cannot be reconstructed from the file.

## Running tests

```bash
pip install pytest
pytest test_core.py
```

## Project structure

```
main.py          entry point — creates the pywebview window
api.py           JS bridge — file dialogs, search, redaction calls
core.py          PDF engine — search, redact, metadata, save
ui/
  index.html     single-page UI
  lib/
    pdf.min.js         PDF.js renderer
    pdf.worker.min.js  PDF.js worker (loaded via blob URL to bypass file:// restrictions)
test_core.py     pytest suite for the PDF engine
```
