<div align="center">
  <h1>redact</h1>
  <p>PDF redaction that actually removes the text.</p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
  [![Platform](https://img.shields.io/badge/Platform-Windows-0078d7.svg?logo=windows)](https://microsoft.com/windows)
</div>

---

Most PDF tools — free or paid — draw black rectangles over text. The characters stay in the file, selectable and extractable. redact uses PyMuPDF to physically remove them at the byte level and strips all metadata that could identify the source.

## Install

```
git clone https://github.com/zntkr/redact.git
cd redact
pip install pymupdf pywebview
python main.py
```

## What it does

- Open a PDF from disk or drop it onto the window
- Select text to redact instantly, or switch to draw mode for images and non-selectable areas
- Search keywords across all pages, cherry-pick matches, batch redact
- Save — a new file is written, the original is untouched

## What it doesn't do

- **Scanned PDFs** — no OCR; keyword search won't find text in images. Use manual area selection instead.
- **Windows** — untested on macOS and Linux.

---

<sub>Built with [PyMuPDF](https://pymupdf.readthedocs.io/) · [pywebview](https://pywebview.flowrl.com/) · [PDF.js](https://mozilla.github.io/pdf.js/)</sub>
