import io
import os
import hashlib
from pathlib import Path
from pypdf import PdfReader

from app.config import ConfigManager, find_tesseract, DEFAULT_LANG_MAP
from app.ocr.ocr_engine import OCREngine
from app.pdf.pdf_utils import render_pdf_page_to_image, get_pdf_page_count, is_image_blank
from app.utils.date_parser import extract_newspaper_info, extract_newspaper_date

def calculate_sha256_bytes(pdf_bytes: bytes) -> str:
    """Calculate SHA-256 hash of in-memory PDF byte stream."""
    return hashlib.sha256(pdf_bytes).hexdigest()

def check_duplicates_batch(files_metadata: list, target_date_sel: str = None) -> dict:
    """Run exact 4-factor duplicate detection and target date filtering on a batch of files.
    
    4-Factor Duplicate Rule:
    Duplicate = (Filename == Filename AND File Size == File Size AND Extension == Extension AND SHA-256 == SHA-256)
    If even ONE factor differs -> NOT DUPLICATE.
    
    Returns dict:
    {
      "eligible": [file_info, ...],
      "duplicates": [file_info, ...]
    }
    """
    target_iso = None
    if target_date_sel:
        target_iso, _ = extract_newspaper_date(target_date_sel)
        if not target_iso:
            target_iso = target_date_sel.strip()

    seen_map = {}
    eligible = []
    duplicates = []

    for file_info in files_metadata:
        filename = file_info.get("filename", "")
        file_size = int(file_info.get("file_size", 0))
        sha256 = file_info.get("sha256", "")
        file_ext = Path(filename).suffix.lower()

        title, iso_date = extract_newspaper_info(filename)
        file_info["newspaper_title"] = title
        file_info["iso_date"] = iso_date

        is_known_date = bool(iso_date and iso_date != "DATE UNKNOWN")

        # 1. Target Date Filter
        if target_iso and is_known_date and iso_date != target_iso:
            file_info["status"] = "OUT-OF-DATE"
            file_info["duplicate_of"] = f"OUT-OF-DATE (Target: {target_date_sel})"
            duplicates.append(file_info)
            continue

        # 2. Exact 4-Factor Duplicate Matching
        exact_key = (filename, file_size, file_ext, sha256)
        if exact_key in seen_map:
            orig = seen_map[exact_key]
            file_info["status"] = "DUPLICATE"
            file_info["duplicate_of"] = orig["filename"]
            duplicates.append(file_info)
        else:
            seen_map[exact_key] = file_info
            file_info["status"] = "UNIQUE"
            eligible.append(file_info)

    return {
        "eligible": eligible,
        "duplicates": duplicates
    }

def inspect_pdf_bytes(pdf_bytes: bytes, filename: str) -> dict:
    """Inspect PDF bytes in-memory to retrieve page count, title, date, and text stream presence."""
    title, iso_date = extract_newspaper_info(filename)
    
    # In-memory page count & text stream inspection
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    
    has_text_stream = False
    for p in reader.pages[:3]: # check first 3 pages
        text = p.extract_text() or ""
        if len(text.strip()) > 30:
            has_text_stream = True
            break

    return {
        "filename": filename,
        "page_count": page_count,
        "newspaper_title": title,
        "iso_date": iso_date,
        "has_text_stream": has_text_stream,
        "is_scanned": not has_text_stream
    }

def process_pdf_page_bytes(pdf_bytes: bytes, filename: str, page_num: int, lang_setting: str = "Auto", dpi: int = 200) -> dict:
    """Process a single page of a PDF byte stream using True Tesseract OCR or direct text stream fallback.
    
    If page is scanned/image-based:
    - Renders page image using pypdfium2 (or poppler fallback) into memory.
    - Runs Tesseract OCREngine for requested language.
    - If Tesseract is missing on server environment, reports explicit OCR engine error.
    """
    title, iso_date = extract_newspaper_info(filename)

    # 1. First check if digital text stream exists on this page
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if 1 <= page_num <= len(reader.pages):
        page = reader.pages[page_num - 1]
        digital_text = (page.extract_text() or "").strip()
    else:
        digital_text = ""

    is_scanned_page = len(digital_text) < 30

    if not is_scanned_page:
        # Digital PDF with embedded text stream
        return {
            "success": True,
            "filename": filename,
            "page_num": page_num,
            "text": digital_text,
            "is_scanned": False,
            "engine_used": "PDF Text Stream",
            "language": lang_setting
        }

    # 2. Page is scanned/image-based -> Requires True OCR!
    tess_cmd = find_tesseract()
    if not tess_cmd or not os.path.exists(tess_cmd):
        # Tesseract binary is NOT available on server
        return {
            "success": False,
            "filename": filename,
            "page_num": page_num,
            "text": "",
            "is_scanned": True,
            "ocr_error": "TESSERACT_UNAVAILABLE",
            "message": "Tesseract OCR binary is unavailable on the server environment. Scanned newspaper pages require Tesseract to extract text."
        }

    # Render single page to PIL Image in memory
    try:
        # Save temp PDF file for pypdfium2 rendering
        temp_pdf = Path(os.environ.get("TMP", "/tmp")) / f"temp_{os.getpid()}_{page_num}.pdf"
        temp_pdf.write_bytes(pdf_bytes)
        try:
            pil_img = render_pdf_page_to_image(str(temp_pdf), page_num=page_num, dpi=dpi)
        finally:
            if temp_pdf.exists():
                temp_pdf.unlink()
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "page_num": page_num,
            "text": "",
            "is_scanned": True,
            "ocr_error": "RENDER_ERROR",
            "message": f"Failed to render PDF page image for OCR: {e}"
        }

    # Perform True OCR via OCREngine
    engine = OCREngine(tesseract_cmd=tess_cmd)
    try:
        ocr_text = engine.perform_ocr(pil_img, lang_setting=lang_setting)
        return {
            "success": True,
            "filename": filename,
            "page_num": page_num,
            "text": ocr_text,
            "is_scanned": True,
            "engine_used": "Tesseract OCR",
            "language": lang_setting
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "page_num": page_num,
            "text": "",
            "is_scanned": True,
            "ocr_error": "OCR_EXECUTION_ERROR",
            "message": f"Tesseract OCR execution error: {e}"
        }

def combine_texts_batch(items: list) -> str:
    """Combine extracted texts into a single structured output string matching TextCombiner."""
    header = "=" * 80 + "\n"
    header += "NEWSPAPER OCR PROCESSOR - COMBINED TEXT OUTPUT\n"
    header += "=" * 80 + "\n\n"

    parts = [header]
    for idx, item in enumerate(items, 1):
        filename = item.get("filename", f"Document_{idx}")
        text = item.get("text", "")
        parts.append(f"--- DOCUMENT {idx}: {filename} ---\n")
        parts.append(text.strip() + "\n\n" + "-" * 50 + "\n\n")

    return "".join(parts)
