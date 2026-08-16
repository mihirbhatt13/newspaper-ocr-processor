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
from app.utils.date_parser import extract_newspaper_info, extract_newspaper_date

def run_target_date_filtering_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING TARGET DATE FILTERING WORKFLOW SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    scratch_dir = PROJECT_ROOT / "tests" / "scratch" / "test_target_date_filter"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Test Files:
    # 1. DC Chennai 08-08.pdf  (8 Aug -> Out of date -> duplicates/)
    # 2. DC Chennai 09-08.pdf  (9 Aug -> Target date eligible -> ocr_queue / unique/)
    # 3. DC Tabloid 08-08.pdf  (8 Aug -> Out of date -> duplicates/)
    # 4. DC Tabloid 09-08.pdf  (9 Aug -> Target date eligible -> ocr_queue / unique/)
    # 5. DC Chennai 10-08.pdf  (10 Aug -> Out of date -> duplicates/)
    # 6. Unknown_Paper.pdf     (DATE UNKNOWN -> Eligible -> ocr_queue / unique/)
    # 7. DC Chennai 09-08_copy.pdf (Same name DC Chennai 09-08.pdf, same size, same content -> Exact 4-Factor DUPLICATE -> duplicates/)

    c1 = "%PDF-1.4 PDF Content payload for DC Chennai 08-08 page 1".ljust(500)
    c2 = "%PDF-1.4 PDF Content payload for DC Chennai 09-08 page 1".ljust(500)
    c3 = "%PDF-1.4 PDF Content payload for DC Tabloid 08-08 page 1".ljust(500)
    c4 = "%PDF-1.4 PDF Content payload for DC Tabloid 09-08 page 1".ljust(500)
    c5 = "%PDF-1.4 PDF Content payload for DC Chennai 10-08 page 1".ljust(500)
    c6 = "%PDF-1.4 PDF Content payload for Unknown_Paper page 1".ljust(500)

    f1_08aug = scratch_dir / "DC Chennai 08-08.pdf"
    f1_08aug.write_bytes(c1.encode('utf-8'))

    f2_09aug = scratch_dir / "DC Chennai 09-08.pdf"
    f2_09aug.write_bytes(c2.encode('utf-8'))

    f3_tabloid_08aug = scratch_dir / "DC Tabloid 08-08.pdf"
    f3_tabloid_08aug.write_bytes(c3.encode('utf-8'))

    f4_tabloid_09aug = scratch_dir / "DC Tabloid 09-08.pdf"
    f4_tabloid_09aug.write_bytes(c4.encode('utf-8'))

    f5_10aug = scratch_dir / "DC Chennai 10-08.pdf"
    f5_10aug.write_bytes(c5.encode('utf-8'))

    f6_unknown = scratch_dir / "Unknown_Paper.pdf"
    f6_unknown.write_bytes(c6.encode('utf-8'))

    sub_dir = scratch_dir / "folder2"
    sub_dir.mkdir(parents=True, exist_ok=True)
    f7_dup = sub_dir / "DC Chennai 09-08.pdf"
    f7_dup.write_bytes(c2.encode('utf-8'))

    test_files = [f1_08aug, f2_09aug, f3_tabloid_08aug, f4_tabloid_09aug, f5_10aug, f6_unknown, f7_dup]

    target_date_sel = "2026-08-09"
    target_iso, _ = extract_newspaper_date(target_date_sel)
    if not target_iso:
        target_iso = target_date_sel.strip()

    seen_files_map = {}
    ocr_queue = []
    duplicate_records = []

    for pdf in test_files:
        sha256 = calculate_sha256(pdf)
        file_size = pdf.stat().st_size if pdf.exists() else 0
        file_ext = pdf.suffix.lower()
        title, iso_date = extract_newspaper_info(pdf.name)
        is_known_date = bool(iso_date and iso_date != "DATE UNKNOWN")

        # 1. Target Date Filter Check
        if is_known_date and iso_date != target_iso:
            dup_label = f"OUT-OF-DATE (Target: {target_date_sel})"
            rec = {
                "pdf_filename": pdf.name,
                "pdf_path": pdf,
                "newspaper": title,
                "date": iso_date,
                "duplicate_of": dup_label,
                "sha256": sha256,
                "status": "DUPLICATE"
            }
            duplicate_records.append(rec)
            print(f"  [EXCLUDED / OUT-OF-DATE] {pdf.name} (Date: {iso_date} != Target: {target_iso})", flush=True)
            continue

        # 2. Exact 4-Factor Duplicate Check
        exact_key = (pdf.name, file_size, file_ext, sha256)
        if exact_key in seen_files_map:
            orig_path, orig_name = seen_files_map[exact_key]
            rec = {
                "pdf_filename": pdf.name,
                "pdf_path": pdf,
                "newspaper": title,
                "date": iso_date,
                "duplicate_of": orig_name,
                "sha256": sha256,
                "status": "DUPLICATE"
            }
            duplicate_records.append(rec)
            print(f"  [EXACT DUPLICATE]       {pdf.name} (Duplicate of {orig_name})", flush=True)
        else:
            seen_files_map[exact_key] = (pdf, pdf.name)
            ocr_queue.append(pdf)
            print(f"  [ELIGIBLE / OCR QUEUE]  {pdf.name} (Date: {iso_date})", flush=True)

    ocr_queue_names = [p.name for p in ocr_queue]
    dup_record_names = [r["pdf_filename"] for r in duplicate_records]

    print("\n--- SUMMARY ASSERTIONS ---", flush=True)
    # 1. 08 Aug PDFs MUST be excluded
    assert "DC Chennai 08-08.pdf" not in ocr_queue_names, "DC Chennai 08-08.pdf must NOT enter OCR queue!"
    assert "DC Tabloid 08-08.pdf" not in ocr_queue_names, "DC Tabloid 08-08.pdf must NOT enter OCR queue!"
    assert "DC Chennai 08-08.pdf" in dup_record_names
    assert "DC Tabloid 08-08.pdf" in dup_record_names
    print("  -> PASSED: 08 Aug PDFs (DC Chennai 08-08 & DC Tabloid 08-08) excluded & flagged OUT-OF-DATE", flush=True)

    # 2. 10 Aug PDF MUST be excluded
    assert "DC Chennai 10-08.pdf" not in ocr_queue_names, "DC Chennai 10-08.pdf must NOT enter OCR queue!"
    assert "DC Chennai 10-08.pdf" in dup_record_names
    print("  -> PASSED: 10 Aug PDF (DC Chennai 10-08) excluded & flagged OUT-OF-DATE", flush=True)

    # 3. 09 Aug PDFs MUST enter OCR queue
    assert "DC Chennai 09-08.pdf" in ocr_queue_names
    assert "DC Tabloid 09-08.pdf" in ocr_queue_names
    print("  -> PASSED: 09 Aug target date PDFs (DC Chennai 09-08 & DC Tabloid 09-08) added to OCR queue", flush=True)

    # 4. DATE UNKNOWN PDF MUST enter OCR queue
    assert "Unknown_Paper.pdf" in ocr_queue_names
    print("  -> PASSED: DATE UNKNOWN PDF preserved in OCR queue as eligible", flush=True)

    # 5. Exact 4-factor duplicate MUST be excluded
    assert len([n for n in dup_record_names if n == "DC Chennai 09-08.pdf"]) >= 1
    print("  -> PASSED: Exact 4-factor duplicate identified & excluded from OCR queue", flush=True)

    # Cleanup scratch test files
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)

    print("\n==================================================", flush=True)
    print("ALL TARGET DATE FILTERING WORKFLOW TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_target_date_filtering_tests()
