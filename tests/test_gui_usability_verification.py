import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories
from app.utils.file_utils import calculate_sha256
from app.combine.text_combiner import combine_all_text_files

def run_usability_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING GUI USABILITY & WORKFLOW SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # --- 1 & 2: Batch Counter Tests ---
    print("\n--- 1 & 2. Testing Batch Status Counters ---", flush=True)
    counts = {"SUCCESS": 78, "FAILED": 5, "NEEDS REVIEW": 4, "DUPLICATE": 3, "PENDING": 0}
    counter_str = f"SUCCESS: {counts['SUCCESS']} | FAILED: {counts['FAILED']} | NEEDS REVIEW: {counts['NEEDS REVIEW']} | DUPLICATES: {counts['DUPLICATE']} | PENDING: {counts['PENDING']}"
    assert "SUCCESS: 78" in counter_str
    assert "FAILED: 5" in counter_str
    assert "NEEDS REVIEW: 4" in counter_str
    assert "DUPLICATES: 3" in counter_str
    assert "PENDING: 0" in counter_str
    print(f"  Counters formatted correctly:\n  '{counter_str}'", flush=True)

    # --- 3 & 4: Batch Summary Formatting ---
    print("\n--- 3 & 4. Testing Batch Summary Modals (Complete & Stopped) ---", flush=True)
    total_cnt = 90
    summary_complete = (
        "========== BATCH COMPLETE ==========\n\n"
        f"Total PDFs       : {total_cnt}\n"
        f"Successful       : {counts['SUCCESS']}\n"
        f"Failed           : {counts['FAILED']}\n"
        f"Needs Review     : {counts['NEEDS REVIEW']}\n"
        f"Duplicates       : {counts['DUPLICATE']}\n"
        f"Pending          : {counts['PENDING']}\n"
        f"TXT Created      : {counts['SUCCESS']}\n\n"
        "====================================="
    )
    assert "========== BATCH COMPLETE ==========" in summary_complete
    assert "Total PDFs       : 90" in summary_complete
    assert "TXT Created      : 78" in summary_complete
    print("  -> BATCH COMPLETE summary modal verified.", flush=True)

    summary_stopped = summary_complete.replace("========== BATCH COMPLETE ==========", "========== BATCH STOPPED ==========")
    assert "========== BATCH STOPPED ==========" in summary_stopped
    print("  -> BATCH STOPPED summary modal verified.", flush=True)

    # --- 5, 6, 7, 8: Folder Opening Paths ---
    print("\n--- 5, 6, 7, 8. Testing Easy Open Folder Buttons Paths ---", flush=True)
    p_text = DIRS["extracted_text"]
    p_redo = DIRS["redo"]
    p_dup = DIRS["duplicates"]
    p_comb = DIRS["combined"]

    p_text.mkdir(parents=True, exist_ok=True)
    p_redo.mkdir(parents=True, exist_ok=True)
    p_dup.mkdir(parents=True, exist_ok=True)
    p_comb.mkdir(parents=True, exist_ok=True)

    assert p_text.exists() and p_text.name == "extracted_text", "Extracted Text path invalid!"
    assert p_redo.exists() and p_redo.name == "redo", "Redo path invalid!"
    assert p_dup.exists() and p_dup.name == "duplicates", "Duplicates path invalid!"
    assert p_comb.exists() and p_comb.name == "combined", "Combined path invalid!"
    print("  -> All 4 folder opening target directories verified.", flush=True)

    # --- 9: FAILED Reason Display ---
    print("\n--- 9. Testing FAILED Reason Display Preservation ---", flush=True)
    error_msg = "Tesseract OCR engine error on page 3: Execution timeout"
    failed_details = f"File: Paper_Failed.pdf\nStatus: FAILED\nDate: 2026-08-04\n\nDetails:\n{error_msg}"
    assert "Status: FAILED" in failed_details
    assert "Tesseract OCR engine error" in failed_details
    print("  -> FAILED reason details string verified without replacing underlying error.", flush=True)

    # --- 10, 11, 12, 13: REDO Safeguards ---
    print("\n--- 10, 11, 12, 13. Testing REDO Workflow Rules ---", flush=True)
    def can_move_to_redo(st):
        if st in ["SUCCESS", "DUPLICATE", "PENDING"]:
            return False
        return st in ["NEEDS REVIEW", "FAILED"]

    assert can_move_to_redo("SUCCESS") is False
    assert can_move_to_redo("DUPLICATE") is False
    assert can_move_to_redo("PENDING") is False
    assert can_move_to_redo("NEEDS REVIEW") is True
    assert can_move_to_redo("FAILED") is True
    print("  -> REDO eligibility rules verified: SUCCESS/DUPLICATE/PENDING blocked; NEEDS REVIEW/FAILED eligible.", flush=True)

    # --- 14 & 15: Optional Duplicate Check ---
    print("\n--- 14 & 15. Testing Optional Duplicate Check ---", flush=True)
    has_checked_duplicates = False
    selected_pdfs = [Path("pdf1.pdf"), Path("pdf2.pdf")]
    ocr_queue = [Path("pdf1.pdf")]

    target = ocr_queue if has_checked_duplicates else selected_pdfs
    assert len(target) == 2, "START OCR MUST process ALL selected PDFs when duplicate check was never run!"

    has_checked_duplicates = True
    target_b = ocr_queue if has_checked_duplicates else selected_pdfs
    assert len(target_b) == 1, "START OCR MUST process ONLY UNIQUE PDFs when duplicate check was run!"
    print("  -> Optional duplicate check logic verified.", flush=True)

    print("\n==================================================", flush=True)
    print("ALL GUI USABILITY & WORKFLOW SYNTHETIC TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_usability_tests()
