import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories
from app.combine.text_combiner import combine_all_text_files

def run_batch_combine_isolation_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING CURRENT-BATCH COMBINE ISOLATION SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()
    ext_dir = DIRS["extracted_text"]
    comb_dir = DIRS["combined"]
    ext_dir.mkdir(parents=True, exist_ok=True)
    comb_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate an "old batch" TXT file inside extracted_text/
    old_file = ext_dir / "Old_Batch_Paper_999_01-01-2025.txt"
    old_file.write_text("Old batch content from previous month\n")

    # Clear previous combined outputs for clean test run
    for fname in ["all_newspaper.txt", "all_newspaper2.txt", "all_newspaper3.txt"]:
        p = comb_dir / fname
        if p.exists():
            p.unlink()

    # --- SYNTHETIC BATCH 1: 10 PDFs (10 SUCCESS) ---
    print("\n--- 1. Testing Synthetic Batch 1 (10 PDFs, 10 SUCCESS) ---", flush=True)
    batch1_pdfs = [f"Batch1_Paper_{i:02d}_07-08-2026.pdf" for i in range(1, 11)]

    # Simulate 10 successful TXT outputs for Batch 1
    for pdf_name in batch1_pdfs:
        stem = Path(pdf_name).stem
        (ext_dir / f"{stem}.txt").write_text(f"Content for Batch 1 PDF {pdf_name}\n")

    s1, c1, p1, m1 = combine_all_text_files(pdf_list=batch1_pdfs)
    assert s1 is True, f"Batch 1 combine failed: {m1}"
    assert Path(p1).name == "all_newspaper.txt", f"Expected all_newspaper.txt, got {Path(p1).name}"
    assert c1 == 10, f"Expected 10 files combined in Batch 1, got {c1}"

    content_b1 = Path(p1).read_text(encoding="utf-8")
    assert "Old batch content" not in content_b1, "CRITICAL: Old batch TXT must NOT be included in Batch 1 combine!"
    assert "BATCH1 PAPER 01" in content_b1.upper(), "Batch 1 content must be present in combined file!"
    print("  -> PASSED: Batch 1 combined exactly 10 current-batch TXT files into all_newspaper.txt without old batch files.", flush=True)


    # --- SYNTHETIC BATCH 2: 10 PDFs (8 SUCCESS, 2 FAILED) ---
    print("\n--- 2. Testing Synthetic Batch 2 (10 PDFs: 8 SUCCESS, 2 FAILED) ---", flush=True)
    batch2_pdfs = [f"Batch2_Paper_{i:02d}_07-08-2026.pdf" for i in range(1, 11)]

    # Simulate 8 successful TXT outputs and 2 failed (no TXT output)
    for pdf_name in batch2_pdfs[:8]:
        stem = Path(pdf_name).stem
        (ext_dir / f"{stem}.txt").write_text(f"Content for Batch 2 PDF {pdf_name}\n")

    s2, c2, p2, m2 = combine_all_text_files(pdf_list=batch2_pdfs)
    assert s2 is True, f"Batch 2 combine failed: {m2}"
    assert Path(p2).name == "all_newspaper2.txt", f"Expected all_newspaper2.txt, got {Path(p2).name}"
    assert c2 == 8, f"Expected 8 files combined in Batch 2, got {c2}"

    assert (comb_dir / "all_newspaper.txt").exists(), "all_newspaper.txt must exist without being overwritten!"
    assert (comb_dir / "all_newspaper2.txt").exists(), "all_newspaper2.txt must exist as a new versioned file!"

    content_b2 = Path(p2).read_text(encoding="utf-8")
    assert "Batch1" not in content_b2, "Batch 1 TXT files must NOT be in Batch 2 combine!"
    assert "Batch2_Paper_09" not in content_b2, "Failed PDF 09 TXT must NOT be in Batch 2 combine!"
    print("  -> PASSED: Batch 2 combined exactly 8 successful TXT files into all_newspaper2.txt without overwriting all_newspaper.txt.", flush=True)


    # --- SYNTHETIC BATCH 3: 5 PDFs (5 SUCCESS) ---
    print("\n--- 3. Testing Synthetic Batch 3 (5 PDFs, 5 SUCCESS) ---", flush=True)
    batch3_pdfs = [f"Batch3_Paper_{i:02d}_07-08-2026.pdf" for i in range(1, 6)]

    for pdf_name in batch3_pdfs:
        stem = Path(pdf_name).stem
        (ext_dir / f"{stem}.txt").write_text(f"Content for Batch 3 PDF {pdf_name}\n")

    s3, c3, p3, m3 = combine_all_text_files(pdf_list=batch3_pdfs)
    assert s3 is True, f"Batch 3 combine failed: {m3}"
    assert Path(p3).name == "all_newspaper3.txt", f"Expected all_newspaper3.txt, got {Path(p3).name}"
    assert c3 == 5, f"Expected 5 files combined in Batch 3, got {c3}"

    assert (comb_dir / "all_newspaper.txt").exists(), "all_newspaper.txt must remain untouched!"
    assert (comb_dir / "all_newspaper2.txt").exists(), "all_newspaper2.txt must remain untouched!"
    assert (comb_dir / "all_newspaper3.txt").exists(), "all_newspaper3.txt must be generated!"
    print("  -> PASSED: Batch 3 combined exactly 5 current-batch TXT files into all_newspaper3.txt while preserving previous combined files.", flush=True)


    # Cleanup synthetic test TXT files
    if old_file.exists():
        old_file.unlink()
    for b in [batch1_pdfs, batch2_pdfs[:8], batch3_pdfs]:
        for pdf_name in b:
            stem = Path(pdf_name).stem
            t = ext_dir / f"{stem}.txt"
            if t.exists():
                t.unlink()

    print("\n==================================================", flush=True)
    print("ALL BATCH COMBINE ISOLATION SYNTHETIC TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_batch_combine_isolation_tests()
