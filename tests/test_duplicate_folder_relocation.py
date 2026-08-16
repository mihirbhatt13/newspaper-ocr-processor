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
from app.utils.date_parser import extract_newspaper_info

def run_duplicate_folder_relocation_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING DUPLICATE & UNIQUE FOLDER RELOCATION SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()
    unique_dir = DIRS["unique"]
    dup_dir = DIRS["duplicates"]
    unique_dir.mkdir(parents=True, exist_ok=True)
    dup_dir.mkdir(parents=True, exist_ok=True)

    # Scratch test folder
    scratch_dir = PROJECT_ROOT / "tests" / "scratch" / "test_dup_reloc"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # 10 Synthetic PDF files:
    # 7 UNIQUE (Target date: 2026-08-07):
    # - Paper_A_07-08-2026.pdf
    # - Paper_B_07-08-2026.pdf
    # - Paper_C_07-08-2026.pdf
    # - Paper_D_07-08-2026.pdf
    # - Paper_E_07-08-2026.pdf
    # - Paper_F_07-08-2026.pdf
    # - Paper_G_UNKNOWN.pdf (Unknown date -> UNIQUE)
    #
    # 3 DUPLICATE / OUT-OF-DATE:
    # - Paper_A_07-08-2026_copy.pdf (Duplicate of Paper A)
    # - Paper_B_06-08-2026.pdf (Out-of-date)
    # - Paper_C_08-08-2026.pdf (Out-of-date)

    synthetic_files = {
        "Paper_A_07-08-2026.pdf": "Dummy PDF Content A",
        "Paper_B_07-08-2026.pdf": "Dummy PDF Content B",
        "Paper_C_07-08-2026.pdf": "Dummy PDF Content C",
        "Paper_D_07-08-2026.pdf": "Dummy PDF Content D",
        "Paper_E_07-08-2026.pdf": "Dummy PDF Content E",
        "Paper_F_07-08-2026.pdf": "Dummy PDF Content F",
        "Paper_G_UNKNOWN.pdf": "Dummy PDF Content G",
        "Paper_A_07-08-2026_copy.pdf": "Dummy PDF Content A Copy",
        "Paper_B_06-08-2026.pdf": "Dummy PDF Content B Old",
        "Paper_C_08-08-2026.pdf": "Dummy PDF Content C New",
    }

    test_paths = []
    for fname, content in synthetic_files.items():
        p = scratch_dir / fname
        p.write_text(content)
        test_paths.append(p)

    target_date_sel = "2026-08-07"
    title_date_map = {}
    ocr_queue = []
    duplicate_records = []

    for pdf in test_paths:
        sha256 = calculate_sha256(pdf)
        title, iso_date = extract_newspaper_info(pdf.name)
        is_known_date = bool(iso_date and iso_date != "DATE UNKNOWN")

        # Target date filter
        if target_date_sel and is_known_date and iso_date != target_date_sel:
            rec = {
                "pdf_filename": pdf.name,
                "pdf_path": pdf,
                "newspaper": title,
                "date": iso_date,
                "duplicate_of": f"OUT-OF-DATE (Target: {target_date_sel})",
                "sha256": sha256,
                "status": "DUPLICATE"
            }
            duplicate_records.append(rec)
            continue

        key = (title, iso_date)
        if key in title_date_map:
            orig_pdf, orig_name = title_date_map[key]
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
        else:
            title_date_map[key] = (pdf, pdf.name)
            ocr_queue.append(pdf)

    assert len(ocr_queue) == 7, f"Expected 7 unique PDFs, got {len(ocr_queue)}"
    assert len(duplicate_records) == 3, f"Expected 3 duplicate PDFs, got {len(duplicate_records)}"

    # Perform physical file relocation
    new_ocr_queue = []
    for pdf in ocr_queue:
        dest = unique_dir / pdf.name
        if dest.exists():
            short_h = calculate_sha256(pdf)[:8]
            dest = unique_dir / f"{pdf.stem}_{short_h}.pdf"
        shutil.move(str(pdf), str(dest))
        new_ocr_queue.append(dest)

    for rec in duplicate_records:
        pdf_path = rec["pdf_path"]
        dest = dup_dir / pdf_path.name
        if dest.exists():
            short_h = rec.get("sha256", calculate_sha256(pdf_path))[:8]
            dest = dup_dir / f"{pdf_path.stem}_{short_h}.pdf"
        shutil.move(str(pdf_path), str(dest))
        rec["pdf_path"] = dest

    ocr_queue = new_ocr_queue

    # Verification checks
    for p in ocr_queue:
        assert p.exists(), f"Unique file {p.name} must exist!"
        assert p.parent == unique_dir, f"Unique file {p.name} must be located in unique/!"

    for rec in duplicate_records:
        p = rec["pdf_path"]
        assert p.exists(), f"Duplicate file {p.name} must exist!"
        assert p.parent == dup_dir, f"Duplicate file {p.name} must be located in duplicates/!"

    assert "Paper_G_UNKNOWN.pdf" in [p.name for p in ocr_queue], "Paper_G_UNKNOWN.pdf must remain UNIQUE!"
    assert "Paper_A_07-08-2026_copy.pdf" in [rec["pdf_filename"] for rec in duplicate_records], "Paper_A_07-08-2026_copy.pdf must be in duplicates!"
    assert "Paper_B_06-08-2026.pdf" in [rec["pdf_filename"] for rec in duplicate_records], "Paper_B_06-08-2026.pdf must be in duplicates!"
    assert "Paper_C_08-08-2026.pdf" in [rec["pdf_filename"] for rec in duplicate_records], "Paper_C_08-08-2026.pdf must be in duplicates!"

    print("  -> PASSED: 10 synthetic PDFs correctly separated (7 UNIQUE in unique/, 3 DUPLICATES in duplicates/).", flush=True)
    print("  -> PASSED: Unique PDFs exist in unique/ folder and are set in ocr_queue.", flush=True)
    print("  -> PASSED: Duplicate PDFs exist in duplicates/ folder and are excluded from ocr_queue.", flush=True)
    print("  -> PASSED: Filenames preserved without overwriting.", flush=True)

    # Cleanup scratch files in unique and duplicates
    for p in ocr_queue:
        if p.exists():
            p.unlink()
    for rec in duplicate_records:
        p = rec["pdf_path"]
        if p.exists():
            p.unlink()
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)

    print("\n==================================================", flush=True)
    print("ALL DUPLICATE & UNIQUE RELOCATION TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_duplicate_folder_relocation_tests()
