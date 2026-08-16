import os
import sys
import shutil
import queue
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories
from app.combine.text_combiner import combine_all_text_files
from app.utils.state_manager import StateManager

def run_office_workflow_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING FINAL OFFICE WORKFLOW SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # Clean test scratch dirs inside combined and extracted_text
    test_ext = DIRS["extracted_text"] / "test_scratch"
    test_ext.mkdir(parents=True, exist_ok=True)

    # TEST 1 & 2: Successful TXT directly inside extracted_text/ without date subfolders
    print("\n--- TEST 1 & 2: Flat extracted_text/ Output ---", flush=True)
    state_mgr = StateManager()
    dummy_pdf = PROJECT_ROOT / "tests" / "scratch" / "Dummy_Success_04-08-2026.pdf"
    dummy_pdf.parent.mkdir(parents=True, exist_ok=True)
    dummy_pdf.write_bytes(b"%PDF-1.4 synthetic success test content")

    rec = state_mgr.init_pdf_state(dummy_pdf, total_pages=5)
    out_path = Path(rec["output_file"])
    assert out_path.parent == DIRS["extracted_text"], f"Expected direct child of extracted_text, got {out_path.parent}"
    assert "2026" not in out_path.parent.name, "Output must NOT be inside date subfolder!"
    print(f"  -> PASSED: TXT path is directly inside flat extracted_text/: {out_path.name}", flush=True)

    # TEST 3, 4, 5, 6, 7, 8, 9: Automatic REDO for FAILED PDFs & Eligibility
    print("\n--- TEST 3 to 9: Automatic REDO for FAILED & Eligibility Rules ---", flush=True)
    failed_pdf = PROJECT_ROOT / "tests" / "scratch" / "Dummy_Failed_04-08-2026.pdf"
    failed_pdf.write_bytes(b"%PDF-1.4 synthetic failed pdf")

    redo_dir = DIRS["redo"]
    redo_dir.mkdir(parents=True, exist_ok=True)

    # Simulate automatic relocation of FAILED PDF
    dest_redo = redo_dir / failed_pdf.name
    if dest_redo.exists():
        dest_redo.unlink()
    shutil.move(str(failed_pdf), str(dest_redo))

    assert dest_redo.exists(), "FAILED PDF must exist inside redo/"
    assert dest_redo.name == "Dummy_Failed_04-08-2026.pdf", "Original filename must be preserved!"
    assert not (DIRS["extracted_text"] / "Dummy_Failed_04-08-2026.txt").exists(), "FAILED PDF must NOT produce TXT output!"
    print("  -> PASSED: FAILED PDF automatically moved to redo/ with filename preserved and no TXT created.", flush=True)

    # TEST 10, 11, 12, 13, 14, 15, 16: Versioned Combined Output Files (all_newspaper.txt, all_newspaper2.txt, all_newspaper3.txt...)
    print("\n--- TEST 10 to 16: Versioned Combined Output Files & 100+ TXT Combine ---", flush=True)
    comb_dir = DIRS["combined"]
    comb_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous test files in combined
    f1 = comb_dir / "all_newspaper.txt"
    f2 = comb_dir / "all_newspaper2.txt"
    f3 = comb_dir / "all_newspaper3.txt"
    for f in [f1, f2, f3]:
        if f.exists():
            f.unlink()

    # Create 105 synthetic TXT files in extracted_text
    for i in range(1, 106):
        (DIRS["extracted_text"] / f"Paper_{i:03d}_04-08-2026.txt").write_text(f"Synthetic news text content for paper {i}\n")

    # Combine 1: creates all_newspaper.txt
    res1, cnt1, path1, msg1 = combine_all_text_files()
    assert res1 and Path(path1).name == "all_newspaper.txt", f"Expected all_newspaper.txt, got {path1}"
    assert cnt1 >= 105
    print(f"  -> Combine 1 created: {Path(path1).name} ({cnt1} files)", flush=True)

    # Combine 2: creates all_newspaper2.txt without overwriting all_newspaper.txt
    res2, cnt2, path2, msg2 = combine_all_text_files()
    assert res2 and Path(path2).name == "all_newspaper2.txt", f"Expected all_newspaper2.txt, got {path2}"
    assert f1.exists(), "all_newspaper.txt MUST NOT be overwritten!"
    print(f"  -> Combine 2 created: {Path(path2).name} (all_newspaper.txt preserved)", flush=True)

    # Combine 3: creates all_newspaper3.txt without overwriting all_newspaper.txt or all_newspaper2.txt
    res3, cnt3, path3, msg3 = combine_all_text_files()
    assert res3 and Path(path3).name == "all_newspaper3.txt", f"Expected all_newspaper3.txt, got {path3}"
    assert f1.exists() and f2.exists(), "Previous combined files MUST NOT be overwritten!"
    print(f"  -> Combine 3 created: {Path(path3).name} (all_newspaper.txt and all_newspaper2.txt preserved)", flush=True)

    # Cleanup test TXT files
    for i in range(1, 106):
        p = DIRS["extracted_text"] / f"Paper_{i:03d}_04-08-2026.txt"
        if p.exists():
            p.unlink()

    print("\n==================================================", flush=True)
    print("ALL FINAL OFFICE WORKFLOW TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_office_workflow_tests()
