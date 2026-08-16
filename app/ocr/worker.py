import os
import time
import gc
from pathlib import Path

from app.pdf.pdf_utils import get_pdf_page_count, render_pdf_page_to_image, is_image_blank
from app.ocr.ocr_engine import OCREngine
from app.utils.state_manager import StateManager
from app.utils.logger import get_logger
from app.utils.file_utils import calculate_sha256
from app.utils.date_parser import extract_newspaper_date

def _worker_process_single_pdf(pdf_path, config_dict, progress_queue=None):
    """Top-level worker wrapper function suitable for ProcessPoolExecutor on Windows."""
    def mp_callback(pdf_name, page_num, total_pages, status_msg):
        if progress_queue is not None:
            try:
                progress_queue.put({
                    "pdf_filename": pdf_name,
                    "current_page": page_num,
                    "total_pages": total_pages,
                    "status_msg": status_msg
                })
            except Exception:
                pass

    callback = mp_callback if progress_queue is not None else None
    return process_pdf_file(pdf_path, config_dict, progress_callback=callback)


def process_pdf_file(pdf_path, config_dict, progress_callback=None):
    """Processes a single PDF file page-by-page with streaming RAM, SHA-256 duplicate check, and date organizing."""
    pdf_filename = Path(pdf_path).name
    logger = get_logger()
    state_mgr = StateManager()
    
    start_time = time.time()
    tesseract_cmd = config_dict.get("tesseract_cmd")
    poppler_path = config_dict.get("poppler_path")
    dpi = config_dict.get("dpi", 200)
    lang_setting = config_dict.get("ocr_language", "Auto")

    ocr_engine = OCREngine(tesseract_cmd=tesseract_cmd)
    
    try:
        total_pages = get_pdf_page_count(pdf_path, poppler_path=poppler_path)
    except Exception as e:
        err_msg = f"Failed to open or count pages in PDF: {e}"
        logger.error(f"[{pdf_filename}] {err_msg}")
        state_mgr.mark_failed(pdf_filename, err_msg)
        return {
            "pdf_filename": pdf_filename,
            "total_pages": 0,
            "processed_pages": 0,
            "status": "FAILED",
            "duration_sec": round(time.time() - start_time, 2),
            "error_message": err_msg
        }

    # Initialize state with SHA-256 hash identity
    rec = state_mgr.init_pdf_state(pdf_path, total_pages, language_used=lang_setting)
    sha256 = rec.get("sha256")
    iso_date = rec.get("date_extracted", "DATE UNKNOWN")

    # Duplicate check: If SHA-256 already exists, skip OCR processing
    if rec.get("status") == "DUPLICATE":
        orig_file = rec.get("original_file", "another PDF")
        dup_msg = f"Duplicate file content (SHA-256 match with {orig_file})"
        logger.info(f"[{pdf_filename}] DUPLICATE DETECTED: {dup_msg}")
        print(f"[{pdf_filename}] DUPLICATE DETECTED: {dup_msg}", flush=True)
        if progress_callback:
            progress_callback(pdf_filename, 0, total_pages, f"DUPLICATE (Matches {orig_file})")
        return {
            "pdf_filename": pdf_filename,
            "sha256": sha256,
            "total_pages": total_pages,
            "processed_pages": 0,
            "status": "DUPLICATE",
            "duration_sec": 0.05,
            "error_message": dup_msg,
            "original_file": orig_file,
            "date_extracted": iso_date
        }

    completed_pages = set(state_mgr.get_completed_pages(pdf_filename, sha256_hash=sha256))
    
    logger.info(f"Starting OCR for '{pdf_filename}' ({total_pages} pages, DPI={dpi}, Lang={lang_setting}, Date={iso_date}). Completed pages so far: {len(completed_pages)}/{total_pages}")
    print(f"[{pdf_filename}] Processing {total_pages} pages (DPI={dpi}, Lang={lang_setting}, Date={iso_date})...", flush=True)
    
    processed_count = len(completed_pages)
    empty_pages_count = 0
    total_extracted_chars = 0
    
    for page_num in range(1, total_pages + 1):
        if page_num in completed_pages:
            logger.info(f"[{pdf_filename}] Page {page_num}/{total_pages} already processed. Skipping.")
            if progress_callback:
                progress_callback(pdf_filename, page_num, total_pages, "Skipped (Already done)")
            continue
            
        page_img = None
        try:
            # 1. Render page to image in RAM
            page_img = render_pdf_page_to_image(pdf_path, page_num, dpi=dpi, poppler_path=poppler_path)
            
            # 2. Blank / Render Corruption Detection (< 0.1% dark ink pixels)
            if is_image_blank(page_img, threshold_pct=0.1):
                empty_pages_count += 1
                warn_msg = f"Page {page_num} rendered as blank/corrupted (0.0% ink pixels)."
                logger.warning(f"[{pdf_filename}] {warn_msg}")
                state_mgr.append_page_text(pdf_filename, page_num, total_pages, f"[WARNING: {warn_msg}]", language_used=lang_setting, sha256_hash=sha256)
                processed_count += 1
                if progress_callback:
                    progress_callback(pdf_filename, page_num, total_pages, "Blank/Corrupt Page")
                continue

            # 3. Perform OCR
            text = ocr_engine.perform_ocr(page_img, lang_setting=lang_setting)
            meaningful_text = text.strip()
            char_count = len(meaningful_text)
            total_extracted_chars += char_count

            if char_count < 25:
                empty_pages_count += 1
                logger.warning(f"[{pdf_filename}] Page {page_num} OCR produced minimal text ({char_count} chars).")
            
            # 4. Append deduplicated page text into date subfolder
            state_mgr.append_page_text(pdf_filename, page_num, total_pages, text, language_used=lang_setting, sha256_hash=sha256)
            processed_count += 1
            
            logger.info(f"[{pdf_filename}] Completed page {page_num}/{total_pages} ({char_count} chars)")
            print(f"  -> [{pdf_filename}] Page {page_num}/{total_pages} done ({char_count} chars)", flush=True)
            
            if progress_callback:
                progress_callback(pdf_filename, page_num, total_pages, "Processing")
                
        except Exception as e:
            logger.error(f"[{pdf_filename}] Error on page {page_num}: {e}")
            state_mgr.mark_failed(pdf_filename, f"Error on page {page_num}: {e}", total_pages=total_pages, sha256_hash=sha256)
            return {
                "pdf_filename": pdf_filename,
                "sha256": sha256,
                "total_pages": total_pages,
                "processed_pages": processed_count,
                "status": "FAILED",
                "duration_sec": round(time.time() - start_time, 2),
                "error_message": f"Error on page {page_num}: {e}",
                "date_extracted": iso_date
            }
        finally:
            if page_img:
                try:
                    page_img.close()
                except Exception:
                    pass
            gc.collect()

    duration = round(time.time() - start_time, 2)
    state_mgr.update_duration(pdf_filename, duration, sha256_hash=sha256)
    
    # 5. Output Validation: Check if PDF rendered blank/corrupt or produced no meaningful OCR text
    # Check text content of output file if pages were skipped
    out_rec = state_mgr.get_file_state(pdf_filename, sha256_hash=sha256)
    out_file_path = Path(out_rec.get("output_file", ""))
    file_char_count = 0
    if out_file_path.exists():
        try:
            with open(out_file_path, "r", encoding="utf-8") as f:
                file_char_count = len(f.read().strip())
        except Exception:
            pass

    if (empty_pages_count >= total_pages or file_char_count < 100) and out_rec.get("status") != "DUPLICATE":

        reason = "PDF rendered blank/corrupt; OCR produced no meaningful text."
        state_mgr.mark_needs_review(pdf_filename, reason, total_pages=total_pages, sha256_hash=sha256)
        logger.warning(f"[{pdf_filename}] Flagged as NEEDS REVIEW: {reason}")
        print(f"[{pdf_filename}] Flagged NEEDS REVIEW: {reason}", flush=True)
        return {
            "pdf_filename": pdf_filename,
            "sha256": sha256,
            "total_pages": total_pages,
            "processed_pages": processed_count,
            "status": "NEEDS REVIEW",
            "duration_sec": duration,
            "error_message": reason,
            "date_extracted": iso_date
        }


    logger.info(f"[{pdf_filename}] Finished OCR successfully in {duration}s")
    print(f"[{pdf_filename}] Finished in {duration}s", flush=True)
    
    return {
        "pdf_filename": pdf_filename,
        "sha256": sha256,
        "total_pages": total_pages,
        "processed_pages": processed_count,
        "status": "SUCCESS",
        "duration_sec": duration,
        "error_message": "",
        "date_extracted": iso_date
    }


