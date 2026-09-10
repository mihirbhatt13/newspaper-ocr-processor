import io
import os
import time
import tempfile
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
    
    If page is scanned/image-based or contains sparse metadata (< 150 chars):
    - Renders page image using pypdfium2 (or poppler fallback) into memory.
    - Runs Tesseract OCREngine for requested language.
    - Returns rich diagnostic metadata (rendered image size, Tesseract path, version, text length).
    """
    title, iso_date = extract_newspaper_info(filename)

    # 1. Check if digital text stream exists on this page
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    if 1 <= page_num <= page_count:
        page = reader.pages[page_num - 1]
        digital_text = (page.extract_text() or "").strip()
    else:
        digital_text = ""

    # A full newspaper page has hundreds/thousands of characters. < 150 chars indicates scanned or header metadata.
    is_scanned_page = len(digital_text) < 150

    tess_cmd = find_tesseract()
    tess_version = "Unavailable"
    if tess_cmd and os.path.exists(tess_cmd):
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tess_cmd
            tess_version = str(pytesseract.get_tesseract_version())
        except Exception:
            tess_version = "Unknown"

    if not is_scanned_page:
        # Digital PDF with rich embedded text stream
        return {
            "success": True,
            "filename": filename,
            "page_num": page_num,
            "page_count": page_count,
            "text": digital_text,
            "text_length": len(digital_text),
            "preview_snippet": digital_text[:200],
            "is_scanned": False,
            "engine_used": "PDF Text Stream",
            "language": lang_setting,
            "img_dims": "N/A (Text Stream)",
            "tess_path": tess_cmd or "N/A",
            "tess_version": tess_version
        }

    # 2. Page is scanned/image-based or sparse -> Requires True OCR!
    if not tess_cmd or not os.path.exists(tess_cmd):
        return {
            "success": False,
            "filename": filename,
            "page_num": page_num,
            "page_count": page_count,
            "text": digital_text,
            "text_length": len(digital_text),
            "preview_snippet": digital_text[:200],
            "is_scanned": True,
            "ocr_error": "TESSERACT_UNAVAILABLE",
            "message": "Tesseract OCR binary is unavailable on the server environment. Scanned newspaper pages require Tesseract to extract text.",
            "img_dims": "N/A",
            "tess_path": "None",
            "tess_version": "None"
        }

    # Render single page to PIL Image in memory using a safe temporary file
    temp_pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(pdf_bytes)
            temp_pdf_path = tf.name
        
        pil_img = render_pdf_page_to_image(temp_pdf_path, page_num=page_num, dpi=dpi)
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "page_num": page_num,
            "page_count": page_count,
            "text": "",
            "text_length": 0,
            "preview_snippet": "",
            "is_scanned": True,
            "ocr_error": "RENDER_ERROR",
            "message": f"Failed to render PDF page image for OCR: {e}",
            "img_dims": "N/A",
            "tess_path": tess_cmd,
            "tess_version": tess_version
        }
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.unlink(temp_pdf_path)
            except Exception:
                pass

    img_dims_str = f"{pil_img.width}x{pil_img.height}"

    # Perform True OCR via OCREngine
    engine = OCREngine(tesseract_cmd=tess_cmd)
    try:
        ocr_text = engine.perform_ocr(pil_img, lang_setting=lang_setting).strip()
        
        # If OCR yields meaningful text or if digital_text was empty/sparse, use OCR result
        final_text = ocr_text if (len(ocr_text) > len(digital_text) or len(ocr_text) >= 10) else digital_text

        return {
            "success": True,
            "filename": filename,
            "page_num": page_num,
            "page_count": page_count,
            "text": final_text,
            "text_length": len(final_text),
            "preview_snippet": final_text[:200],
            "is_scanned": True,
            "engine_used": "Tesseract OCR",
            "language": lang_setting,
            "img_dims": img_dims_str,
            "tess_path": tess_cmd,
            "tess_version": tess_version
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "page_num": page_num,
            "page_count": page_count,
            "text": digital_text,
            "text_length": len(digital_text),
            "preview_snippet": digital_text[:200],
            "is_scanned": True,
            "ocr_error": "OCR_EXECUTION_ERROR",
            "message": f"Tesseract OCR execution error: {e}",
            "img_dims": img_dims_str,
            "tess_path": tess_cmd,
            "tess_version": tess_version
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


import json
import threading
import uuid

class BatchJobManager:
    """Manages server-side asynchronous batch PDF OCR jobs stored in /tmp/batch_jobs/."""
    
    BASE_DIR = Path(tempfile.gettempdir()) / "batch_jobs"

    @classmethod
    def _get_job_dir(cls, job_id: str) -> Path:
        return cls.BASE_DIR / job_id

    @classmethod
    def create_job(cls) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_dir = cls._get_job_dir(job_id)
        (job_dir / "input").mkdir(parents=True, exist_ok=True)
        (job_dir / "output").mkdir(parents=True, exist_ok=True)
        
        status_data = {
            "job_id": job_id,
            "status": "INITIALIZING",
            "created_at": time.time(),
            "total_pdfs": 0,
            "completed_pdfs": 0,
            "failed_pdfs": 0,
            "total_pages": 0,
            "processed_pages": 0,
            "current_pdf": "",
            "current_page": 0,
            "ocr_language": "Auto",
            "files": {},
            "combined_text": ""
        }
        cls._write_status(job_id, status_data)
        return job_id

    @classmethod
    def _write_status(cls, job_id: str, status_data: dict):
        job_dir = cls._get_job_dir(job_id)
        status_file = job_dir / "status.json"
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

    @classmethod
    def get_job_status(cls, job_id: str) -> dict:
        status_file = cls._get_job_dir(job_id) / "status.json"
        if not status_file.exists():
            return {"job_id": job_id, "status": "NOT_FOUND", "error": "Job ID not found."}
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"job_id": job_id, "status": "ERROR", "error": str(e)}

    @classmethod
    def save_file(cls, job_id: str, filename: str, file_bytes: bytes) -> dict:
        job_dir = cls._get_job_dir(job_id)
        if not job_dir.exists():
            return {"success": False, "error": "Job directory does not exist."}
        
        file_path = job_dir / "input" / filename
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        
        # Read page count
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
        except Exception:
            page_count = 0
            
        status = cls.get_job_status(job_id)
        status["files"][filename] = {
            "filename": filename,
            "file_size": len(file_bytes),
            "page_count": page_count,
            "status": "PENDING",
            "extracted_text": ""
        }
        status["total_pdfs"] = len(status["files"])
        status["total_pages"] = sum(f["page_count"] for f in status["files"].values())
        cls._write_status(job_id, status)
        return {"success": True, "filename": filename, "page_count": page_count}

    @classmethod
    def start_job(cls, job_id: str, ocr_language: str = "Auto") -> dict:
        status = cls.get_job_status(job_id)
        if status.get("status") in ["PROCESSING", "COMPLETED"]:
            return {"success": True, "message": f"Job already {status.get('status')}"}
        
        status["status"] = "PROCESSING"
        status["ocr_language"] = ocr_language
        cls._write_status(job_id, status)
        
        t = threading.Thread(target=cls._run_worker, args=(job_id, ocr_language), daemon=True)
        t.start()
        return {"success": True, "job_id": job_id, "status": "PROCESSING"}

    @classmethod
    def _run_worker(cls, job_id: str, ocr_language: str):
        job_dir = cls._get_job_dir(job_id)
        status = cls.get_job_status(job_id)
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        
        tess_cmd = find_tesseract()
        engine = OCREngine(tesseract_cmd=tess_cmd) if (tess_cmd and os.path.exists(tess_cmd)) else None
        
        file_names = list(status["files"].keys())
        
        num_workers = min(os.cpu_count() or 2, 4)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        for filename in file_names:
            file_info = status["files"][filename]
            if file_info["status"] in ["SUCCESS", "COMPLETED"]:
                continue
            
            status["current_pdf"] = filename
            file_info["status"] = "PROCESSING..."
            cls._write_status(job_id, status)
            
            pdf_path = input_dir / filename
            if not pdf_path.exists():
                file_info["status"] = "FAILED"
                status["failed_pdfs"] += 1
                cls._write_status(job_id, status)
                continue
            
            try:
                reader = PdfReader(str(pdf_path))
                page_count = len(reader.pages)
            except Exception as e:
                file_info["status"] = "FAILED"
                file_info["error"] = str(e)
                status["failed_pdfs"] += 1
                cls._write_status(job_id, status)
                continue

            def process_page_task(p_num):
                p_text = ""
                try:
                    if p_num <= len(reader.pages):
                        p_text = (reader.pages[p_num - 1].extract_text() or "").strip()
                except Exception:
                    p_text = ""
                
                if len(p_text) < 150 and engine:
                    try:
                        pil_img = render_pdf_page_to_image(str(pdf_path), page_num=p_num, dpi=200)
                        ocr_res = engine.perform_ocr(pil_img, lang_setting=ocr_language).strip()
                        if len(ocr_res) > len(p_text) or len(ocr_res) >= 10:
                            p_text = ocr_res
                    except Exception as ocr_err:
                        print(f"Parallel OCR error on {filename} page {p_num}: {ocr_err}")
                return p_num, p_text

            page_results = {}
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(process_page_task, p): p for p in range(1, page_count + 1)}
                for future in as_completed(futures):
                    p_num, p_text = future.result()
                    page_results[p_num] = p_text
                    status["current_page"] = p_num
                    status["processed_pages"] += 1
                    cls._write_status(job_id, status)

            full_pdf_text = ""
            for p in range(1, page_count + 1):
                full_pdf_text += f"\n--- PAGE {p} ---\n" + page_results.get(p, "")

            file_info["status"] = "SUCCESS"
            file_info["extracted_text"] = full_pdf_text.strip()
            status["completed_pdfs"] += 1
            
            # Write individual output TXT
            out_file = output_dir / f"{filename}.txt"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(file_info["extracted_text"])
                
            cls._write_status(job_id, status)

        # Generate combined text result
        combined_items = []
        for filename in file_names:
            txt_path = output_dir / f"{filename}.txt"
            if txt_path.exists():
                with open(txt_path, "r", encoding="utf-8") as f:
                    combined_items.append({"filename": filename, "text": f.read()})
                    
        status["combined_text"] = combine_texts_batch(combined_items)
        status["status"] = "COMPLETED"
        status["current_pdf"] = "Complete"
        cls._write_status(job_id, status)

    @classmethod
    def get_job_result(cls, job_id: str) -> dict:
        status = cls.get_job_status(job_id)
        if status.get("status") == "NOT_FOUND":
            return {"success": False, "error": "Job not found"}
        return {
            "success": True,
            "status": status.get("status"),
            "combined_text": status.get("combined_text", ""),
            "files": status.get("files", {})
        }

