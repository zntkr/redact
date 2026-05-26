"""pywebview JS bridge — exposes Python PDF operations to the frontend."""

from __future__ import annotations

import base64
import os
import re

import fitz
import webview

from core import (
    has_text_layer,
    search_all_pages,
    redact_areas,
    clean_metadata,
    save_pdf,
)


import uuid

class API:
    _tabs: dict[str, dict]
    _window: webview.Window | None

    def __init__(self) -> None:
        self._tabs = {}
        self._uploads: dict[str, dict] = {}
        self._window = None

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def get_worker_src(self) -> str:
        # Returned as a string so JS can create a blob URL — avoids file:// worker restrictions.
        worker_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "ui", "lib", "pdf.worker.min.js"
        )
        with open(worker_path, encoding="utf-8") as f:
            return f.read()

    def open_pdf_dialog(self) -> dict | None:
        assert self._window is not None

        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=('PDF Dosyaları (*.pdf)', 'Tüm Dosyalar (*.*)')
        )
        if not result:
            return None

        return self._load_pdf_file(result[0])

    def open_dropped_pdf(self, path: str) -> dict | None:
        if not path or not os.path.exists(path):
            return {"error": "Dosya bulunamadı"}
        return self._load_pdf_file(path)

    def start_file_upload(self, filename: str) -> str:
        token = str(uuid.uuid4())
        temp_path = os.path.join(os.path.expanduser("~"), ".pdf_redactor_temp_" + token + ".pdf")
        self._uploads[token] = {
            "filename": filename,
            "path": temp_path,
            "file": open(temp_path, "wb")
        }
        return token

    def upload_chunk(self, token: str, b64_data: str) -> bool:
        if token in self._uploads:
            import base64
            self._uploads[token]["file"].write(base64.b64decode(b64_data))
            return True
        return False

    def finish_file_upload(self, token: str) -> dict | None:
        if token not in self._uploads:
            return {"error": "Yükleme bulunamadı"}
        
        upload = self._uploads.pop(token)
        upload["file"].close()
        temp_path = upload["path"]

        result = self._load_pdf_file(temp_path)
        if result.get("error"):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return result

        result["filename"] = upload["filename"]
        if result.get("tab_id") in self._tabs:
            self._tabs[result["tab_id"]]["filename"] = upload["filename"]
        return result

    def _load_pdf_file(self, path: str) -> dict:
        try:
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            return {"error": f"PDF açılamadı: {e}"}

        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        del pdf_bytes

        tab_id = str(uuid.uuid4())
        self._tabs[tab_id] = {
            "doc": doc,
            "path": path,
            "filename": os.path.basename(path)
        }

        return {
            "tab_id":         tab_id,
            "filename":       os.path.basename(path),
            "page_count":     len(doc),
            "has_text_layer": has_text_layer(doc),
            "pdf_data":       pdf_b64,
        }

    def search_text(
        self,
        tab_id: str,
        term: str,
        case_sensitive: bool = False,
        whole_word:     bool = False,
    ) -> dict:
        if tab_id not in self._tabs:
            return {"error": "Açık sekme bulunamadı"}
        
        doc = self._tabs[tab_id]["doc"]
        
        raw_terms = re.split(r'[,\n]+', term)
        terms = [t.strip() for t in raw_terms if t.strip()]
        
        if not terms:
            return {"error": "Aranacak metin boş"}

        hits  = search_all_pages(doc, terms, case_sensitive, whole_word)
        total = sum(h["count"] for h in hits)

        return {
            "term":           term,
            "total":          total,
            "page_count":     len(hits),
            "pages":          hits,
            "case_sensitive": case_sensitive,
            "whole_word":     whole_word,
        }

    def apply_combined_redactions(self, tab_id: str, pending_rects: list, queue: list) -> dict:
        assert self._window is not None

        # Pop immediately so concurrent calls cannot share the same doc.
        tab_data = self._tabs.pop(tab_id, None)
        if tab_data is None:
            return {"success": False, "error": "Açık sekme bulunamadı"}

        if not pending_rects and not queue:
            self._tabs[tab_id] = tab_data
            return {"success": False, "error": "Uygulanacak işlem yok (kuyruk ve seçim boş)"}

        doc = tab_data["doc"]
        path = tab_data["path"]
        
        summary: list[dict] = []
        total_redacted = 0
        pages_affected: set[int] = set()

        all_rects = []
        if pending_rects:
            all_rects.extend(pending_rects)
            summary.append({"term": "[Manuel Seçim Alanları]", "count": len(pending_rects)})

        for item in queue:
            queue_rects = item.get("rects", [])
            all_rects.extend(queue_rects)
            summary.append({"term": item["term"], "count": len(queue_rects)})

        if all_rects:
            page_rects: dict[int, list] = {}
            for r in all_rects:
                pi = int(r["page_index"])
                page_rects.setdefault(pi, []).append(
                    (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])
                )

            for page_index, pr_list in page_rects.items():
                redact_areas(doc, page_index, pr_list)
                pages_affected.add(page_index + 1)
                total_redacted += len(pr_list)

        result = self._save_dialog(path, doc)
        if result["success"]:
            result.update({
                "total":          total_redacted,
                "pages_affected": sorted(pages_affected),
                "summary":        summary,
            })
        else:
            # User cancelled — restore the tab so they can try again.
            self._tabs[tab_id] = tab_data
        return result

    def _save_dialog(self, source_path: str, doc: fitz.Document) -> dict:
        assert self._window is not None

        base_name    = os.path.splitext(os.path.basename(source_path))[0]
        default_save = base_name + "_redacted.pdf"

        save_result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=default_save,
            file_types=('PDF Dosyaları (*.pdf)',)
        )
        if not save_result:
            return {"success": False, "error": "Kaydetme iptal edildi"}

        out_path: str = save_result if isinstance(save_result, str) else save_result[0]
        if not out_path.lower().endswith(".pdf"):
            out_path += ".pdf"

        clean_metadata(doc)
        save_pdf(doc, out_path)
        doc.close()

        return {"success": True, "path": out_path}
