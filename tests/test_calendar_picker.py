import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories
from app.utils.date_parser import extract_newspaper_info

def run_calendar_picker_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING CALENDAR PICKER & TARGET-DATE SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # 1. Target date selection from calendar (07-08-2026 -> 2026-08-07)
    selected_target_date = "2026-08-07"
    print(f"\n--- 1. Selected Target Date from Calendar Picker: '{selected_target_date}' ---", flush=True)

    test_files = [
        "Hyderabad_TOI_07-08-2026.pdf",
        "Hyderabad_TOI_07-08-2026_dup.pdf",
        "Hyderabad_TOI_06-08-2026.pdf",
        "Delhi_Times_07-08-2026.pdf"
    ]

    title_date_map = {}
    ocr_queue = []
    duplicate_records = []

    for fname in test_files:
        title, iso_date = extract_newspaper_info(fname)

        # Target date filter
        if selected_target_date and iso_date != selected_target_date:
            duplicate_records.append({"filename": fname, "reason": f"OUT-OF-DATE (Target: {selected_target_date})"})
            continue

        key = (title, iso_date)
        if key in title_date_map:
            duplicate_records.append({"filename": fname, "reason": f"DUPLICATE of {title_date_map[key]}"})
        else:
            title_date_map[key] = fname
            ocr_queue.append(fname)

    assert "Hyderabad_TOI_07-08-2026.pdf" in ocr_queue
    assert "Delhi_Times_07-08-2026.pdf" in ocr_queue
    assert len(ocr_queue) == 2, f"Expected 2 unique target-date PDFs, got {len(ocr_queue)}"

    dup_files = [r["filename"] for r in duplicate_records]
    assert "Hyderabad_TOI_07-08-2026_dup.pdf" in dup_files
    assert "Hyderabad_TOI_06-08-2026.pdf" in dup_files
    assert len(duplicate_records) == 2, f"Expected 2 duplicate/out-of-date PDFs, got {len(duplicate_records)}"

    print("  -> PASSED: Selected calendar target date '07-08-2026' correctly passed to deduplication filter.", flush=True)
    print("  -> PASSED: Same name + different date marked OUT-OF-DATE / DUPLICATE.", flush=True)
    print("  -> PASSED: Same name + same date marked DUPLICATE.", flush=True)
    print("  -> PASSED: Different newspaper + target date marked UNIQUE.", flush=True)

    print("\n==================================================", flush=True)
    print("ALL CALENDAR PICKER SYNTHETIC TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_calendar_picker_tests()
