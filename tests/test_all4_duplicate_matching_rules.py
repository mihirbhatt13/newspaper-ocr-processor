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

def run_all4_duplicate_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING ALL-4 DUPLICATE MATCHING CRITERIA SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    scratch_dir = PROJECT_ROOT / "tests" / "scratch" / "test_dup_all4"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Test PDFs setup for 90-page / multi-folder scenarios with target date 2026-08-09:
    # 1. Base File: Newspaper_A_09-08-2026.pdf (Content 1, Size X)
    # 2. Exact Dup: Newspaper_A_09-08-2026.pdf in Subfolder (Same Name, Same Size, Same Extension, Same Content Hash) -> DUPLICATE
    # 3. Diff Size: Newspaper_B_09-08-2026.pdf (Same Name Newspaper_B, Diff Size) -> NOT DUPLICATE
    # 4. Diff Content: Newspaper_C_09-08-2026.pdf vs Newspaper_C_09-08-2026_alt.pdf (Same Name Newspaper_C, Same Size, Diff Content Hash) -> NOT DUPLICATE
    # 5. Diff Name: Newspaper_D_09-08-2026.pdf vs Newspaper_E_09-08-2026.pdf (Diff Name, Same Size, Same Content Hash) -> NOT DUPLICATE
    # 6. Same Name/Size/Content, Diff Date: Newspaper_F_09-08-2026.pdf vs Newspaper_F_09-08-2026_copy.pdf (Same Name, Same Size, Same Content) -> DUPLICATE

    content1 = "Standard PDF content for newspaper paper A page 1 2 3"
    content1_padded = content1.ljust(500) # 500 bytes
    content2_diff_size = content1.ljust(650) # 650 bytes (diff size)
    content3_diff_content = "Different content for newspaper C with identical 500b length!".ljust(500) # 500 bytes (diff content, same size)

    f1 = scratch_dir / "Newspaper_A_09-08-2026.pdf"
    f1.write_bytes(content1_padded.encode('utf-8'))

    sub_dir = scratch_dir / "folder2"
    sub_dir.mkdir(parents=True, exist_ok=True)
    f2_exact_dup = sub_dir / "Newspaper_A_09-08-2026.pdf" # Same name, same size, same ext, same content
    f2_exact_dup.write_bytes(content1_padded.encode('utf-8'))

    f3_orig = scratch_dir / "Newspaper_B_09-08-2026.pdf"
    f3_orig.write_bytes(content1_padded.encode('utf-8'))
    f3_diff_size = sub_dir / "Newspaper_B_09-08-2026.pdf" # Same name, diff size
    f3_diff_size.write_bytes(content2_diff_size.encode('utf-8'))

    f4_orig = scratch_dir / "Newspaper_C_09-08-2026.pdf"
    f4_orig.write_bytes(content1_padded.encode('utf-8'))
    f4_diff_content = sub_dir / "Newspaper_C_09-08-2026.pdf" # Same name, same size, diff content
    f4_diff_content.write_bytes(content3_diff_content.encode('utf-8'))

    f5_name_d = scratch_dir / "Newspaper_D_09-08-2026.pdf"
    f5_name_d.write_bytes(content1_padded.encode('utf-8'))
    f5_name_e = scratch_dir / "Newspaper_E_09-08-2026.pdf" # Diff name, same size, same content
    f5_name_e.write_bytes(content1_padded.encode('utf-8'))

    test_files = [f1, f2_exact_dup, f3_orig, f3_diff_size, f4_orig, f4_diff_content, f5_name_d, f5_name_e]

    seen_files_map = {}
    ocr_queue = []
    duplicate_records = []

    target_date_sel = "2026-08-09"

    print("\nProcessing PDF files against Target Date: 2026-08-09...\n", flush=True)

    for pdf in test_files:
        sha256 = calculate_sha256(pdf)
        file_size = pdf.stat().st_size
        file_ext = pdf.suffix.lower()
        title, iso_date = extract_newspaper_info(pdf.name)

        exact_key = (pdf.name, file_size, file_ext, sha256)
        if exact_key in seen_files_map:
            orig_pdf, orig_name = seen_files_map[exact_key]
            rec = {
                "pdf_filename": str(pdf.relative_to(scratch_dir)),
                "pdf_path": pdf,
                "newspaper": title,
                "date": iso_date,
                "duplicate_of": orig_name,
                "sha256": sha256,
                "status": "DUPLICATE"
            }
            duplicate_records.append(rec)
            print(f"[DUPLICATE]     {pdf.relative_to(scratch_dir)} -> Matches name ({pdf.name}), size ({file_size}b), ext ({file_ext}), and content hash ({sha256[:8]}) of {orig_name}", flush=True)
        else:
            seen_files_map[exact_key] = (pdf, pdf.name)
            ocr_queue.append(pdf)
            print(f"[NOT DUPLICATE] {pdf.relative_to(scratch_dir)} (Added to OCR Queue)", flush=True)

    print("\n--- Summary Verification ---", flush=True)
    dup_files = [r["pdf_filename"] for r in duplicate_records]
    unique_files = [str(p.relative_to(scratch_dir)) for p in ocr_queue]

    # Rule 1: Same name + same size + same ext + same content -> DUPLICATE
    assert f"folder2{os.sep}Newspaper_A_09-08-2026.pdf" in dup_files, "Exact copy Newspaper_A in folder2 must be DUPLICATE!"
    print("  -> PASSED Example 1: Same name + same size + same content -> DUPLICATE", flush=True)

    # Rule 2: Same name + different size -> NOT DUPLICATE
    assert f"folder2{os.sep}Newspaper_B_09-08-2026.pdf" in unique_files, "Different size Newspaper_B must NOT be duplicate!"
    print("  -> PASSED Example 2: Same name + different size -> NOT DUPLICATE", flush=True)

    # Rule 3: Same name + same size + different content -> NOT DUPLICATE
    assert f"folder2{os.sep}Newspaper_C_09-08-2026.pdf" in unique_files, "Different content Newspaper_C must NOT be duplicate!"
    print("  -> PASSED Example 3: Same name + same size + different content -> NOT DUPLICATE", flush=True)

    # Rule 4: Different name + same size + same content -> NOT DUPLICATE
    assert "Newspaper_E_09-08-2026.pdf" in unique_files, "Different filename Newspaper_E must NOT be duplicate!"
    print("  -> PASSED Example 4: Different name + same size + same content -> NOT DUPLICATE", flush=True)

    # Cleanup scratch test files
    shutil.rmtree(scratch_dir)

    print("\n==================================================", flush=True)
    print("ALL 4 DUPLICATE MATCHING CRITERIA TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_all4_duplicate_tests()
