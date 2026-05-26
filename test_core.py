import os
import fitz
import pytest
from core import (
    _turkish_casefold,
    _strip_word_punct,
    _search_page,
    search_all_pages,
    redact_areas,
    clean_metadata,
)

def test_turkish_casefold():
    assert _turkish_casefold("İSTANBUL") == "istanbul"
    assert _turkish_casefold("Isparta") == "isparta"
    assert _turkish_casefold("ıslak") == "islak"
    assert _turkish_casefold("iğne") == "iğne"

def test_strip_word_punct():
    assert _strip_word_punct("Kelime.") == "Kelime"
    assert _strip_word_punct("(Parantez)") == "Parantez"
    assert _strip_word_punct("Virgül,") == "Virgül"
    assert _strip_word_punct("!Ünlem!") == "Ünlem"
    assert _strip_word_punct("Normal") == "Normal"


@pytest.fixture
def sample_pdf_path(tmp_path):
    pdf_path = tmp_path / "test_doc.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Satır 1
    page.insert_text((50, 50), "Ali ata bak.", fontsize=12)
    # Satır 2
    page.insert_text((50, 70), "ALI ata bak.", fontsize=12)
    # Satır 3
    page.insert_text((50, 90), "kalibrasyon", fontsize=12)
    # Satır 4
    page.insert_text((50, 110), "GIZLI BILGI", fontsize=12)
    
    doc.save(pdf_path)
    doc.close()
    return str(pdf_path)


def test_search_case_insensitive(sample_pdf_path):
    doc = fitz.open(sample_pdf_path)
    # "ali" aranırsa (case_sensitive=False, whole_word=False)
    # "Ali", "ALI", "kalibrasyon" (içindeki ali) bulunmalı. Toplam 3.
    results = search_all_pages(doc, ["ali"], case_sensitive=False, whole_word=False)
    assert len(results) == 1
    assert results[0]["count"] == 3
    doc.close()

def test_search_case_sensitive(sample_pdf_path):
    doc = fitz.open(sample_pdf_path)
    # "ALI" aranırsa case_sensitive=True, whole_word=False
    # Sadece "ALI" satırında bulunmalı
    results = search_all_pages(doc, ["ALI"], case_sensitive=True, whole_word=False)
    assert len(results) == 1
    assert results[0]["count"] == 1
    doc.close()

def test_search_whole_word(sample_pdf_path):
    doc = fitz.open(sample_pdf_path)
    # "ali" aranırsa case_sensitive=False, whole_word=True
    # "Ali" ve "ALI" bulunmalı, ama "kalibrasyon" bulunmamalı
    results = search_all_pages(doc, ["ali"], case_sensitive=False, whole_word=True)
    assert len(results) == 1
    assert results[0]["count"] == 2
    doc.close()


def test_redact_areas(sample_pdf_path):
    doc = fitz.open(sample_pdf_path)
    
    # "Ali ata bak." -> (50, 50)'de yazılı. (x0, y0) noktası baseline'a denk gelir, yani karakterler y=50'nin biraz üstünde.
    # Harflerin bounding box'ını içine alacak bir kutu çizelim. 
    # insert_text'te 50, 50 sol-alt(baseline) noktasıdır. Font size 12.
    # Yani y ekseni ~38 ile 52 arasında bir yerlerdedir.
    rect = [45, 35, 75, 55]  # x0, y0, x1, y1
    redact_areas(doc, 0, [rect])
    
    out_path = sample_pdf_path + "_area.pdf"
    doc.save(out_path, garbage=4, deflate=True, clean=True)
    doc.close()
    
    doc_check = fitz.open(out_path)
    text = doc_check[0].get_text()
    doc_check.close()
    
    assert "Ali" not in text
    assert "ata" in text
    
    if os.path.exists(out_path):
        os.remove(out_path)


def test_clean_metadata(sample_pdf_path):
    doc = fitz.open(sample_pdf_path)
    # Metadata ekleyelim
    doc.set_metadata({"author": "Hacker", "title": "Çok Gizli"})
    
    # Temizle
    clean_metadata(doc)
    
    meta: dict = doc.metadata  # type: ignore[assignment]
    assert meta["author"] == ""
    assert meta["title"] == ""
    
    doc.close()


def test_search_whole_word_case_sensitive(sample_pdf_path):
    doc = fitz.open(sample_pdf_path)
    # "ALI" aranırsa case_sensitive=True, whole_word=True
    # "ALI" bulmalı
    results = search_all_pages(doc, ["ALI"], case_sensitive=True, whole_word=True)
    assert len(results) == 1
    assert results[0]["count"] == 1
    doc.close()


def test_has_text_layer(sample_pdf_path, tmp_path):
    from core import has_text_layer
    doc = fitz.open(sample_pdf_path)
    assert has_text_layer(doc) is True
    doc.close()
    
    # Empty PDF test
    empty_pdf = tmp_path / "empty.pdf"
    doc2 = fitz.open()
    doc2.new_page()
    doc2.save(empty_pdf)
    doc2.close()
    
    doc3 = fitz.open(empty_pdf)
    assert has_text_layer(doc3) is False
    doc3.close()


def test_open_and_save_pdf(sample_pdf_path, tmp_path):
    from core import open_pdf, save_pdf
    
    # open_pdf with invalid path
    with pytest.raises(FileNotFoundError):
        open_pdf("nonexistent_file.pdf")
        
    # open_pdf valid
    doc = open_pdf(sample_pdf_path)
    assert doc is not None
    
    # save_pdf
    out_path = str(tmp_path / "saved.pdf")
    save_pdf(doc, out_path)
    assert os.path.exists(out_path)


def test_clean_metadata_exception(sample_pdf_path):
    from unittest.mock import patch
    doc = fitz.open(sample_pdf_path)
    
    with patch("fitz.Document.del_xml_metadata", side_effect=Exception("Mock error")):
        clean_metadata(doc)
    
    meta: dict = doc.metadata  # type: ignore[assignment]
    assert meta["author"] == ""
    doc.close()
