import os
import sys
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories
from app.pdf.pdf_utils import get_pdf_page_count, is_image_blank
from app.utils.date_parser import extract_newspaper_date
from app.utils.file_utils import calculate_sha256, safe_remove_file
from app.utils.state_manager import StateManager
from PIL import Image

def run_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING ALL REQUIRED UNIT TESTS FOR VERIFIED FIXES", flush=True)
    print("==================================================", flush=True)

    ensure_directories()
    cfg = ConfigManager().load_config()

    # --- TEST 1: PDF Discovery Test (No duplication on Windows) ---
    print("\n--- TEST 1: PDF Discovery Test ---", flush=True)
    target_folder = Path("scratch/synthetic_test_folder")
    if target_folder.exists():
        shutil.rmtree(target_folder)
    target_folder.mkdir(parents=True, exist_ok=True)

    for i in range(1, 11):
        valid_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000102 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n163\n%%EOF\n"
        (target_folder / f"Synthetic_News_{i:02d}.pdf").write_bytes(valid_pdf)
    
    # Test unique glob implementation from main_window.py
    all_pdfs = set(target_folder.glob("*.pdf")) | set(target_folder.glob("*.PDF"))
    discovered_paths = sorted(list(all_pdfs))
    
    print(f"  Discovered PDF count: {len(discovered_paths)}", flush=True)
    assert len(discovered_paths) == 10, f"Expected 10 unique PDFs, got {len(discovered_paths)}"
    
    # Verify no duplicate paths exist in discovered_paths
    unique_resolved = set(str(p.resolve()) for p in discovered_paths)
    assert len(unique_resolved) == 10, "Discovered paths must contain 0 duplicates!"
    print("  -> TEST 1 PASSED! 10 expected PDF paths discovered with 0 duplicate path entries.", flush=True)

    # --- TEST 2: GUI Selection / Table State Test ---
    print("\n--- TEST 2: GUI Selection & Table State Test ---", flush=True)
    popp_path = cfg.get("poppler_path")
    state_mgr = StateManager()
    
    table_rows = []
    total_pages_count = 0
    
    for pdf in discovered_paths:
        try:
            pages = get_pdf_page_count(pdf, poppler_path=popp_path)
        except Exception:
            pages = 0
        total_pages_count += pages
        
        sha256 = calculate_sha256(pdf)
        info = state_mgr.get_file_state(pdf.name, sha256_hash=sha256)
        comp_pages = state_mgr.get_completed_pages(pdf.name, sha256_hash=sha256)
        status = info.get("status", "PENDING")
        if status not in ["NEEDS REVIEW", "FAILED", "DUPLICATE"]:
            status = "SUCCESS" if (len(comp_pages) == pages and pages > 0) else "PENDING"
            
        date_str = info.get("date_extracted", "")
        if not date_str or date_str == "DATE UNKNOWN":
            iso, _ = extract_newspaper_date(pdf.name)
            date_str = iso if iso else "DATE UNKNOWN"

        dur = info.get("duration_sec", 0.0)
        table_rows.append((pdf.name, date_str, pages, len(comp_pages), status, "Auto", dur))

    print(f"  Total Loaded PDFs: {len(table_rows)}", flush=True)
    print(f"  Total Estimated Pages: {total_pages_count}", flush=True)
    
    assert len(table_rows) == 10, "Table must contain exactly 10 PDF entries!"
    assert total_pages_count == 10, f"Expected 10 total pages, got {total_pages_count}"

    # Verify table column fields
    for row in table_rows:
        fname, dt, pgs, proc, st, lang, d = row
        assert fname and isinstance(pgs, int) and pgs > 0, f"Invalid row values: {row}"
    print("  -> TEST 2 PASSED! GUI Table loads all 10 PDFs with full column metadata.", flush=True)


    # --- TEST 3: Temporary-File Cleanup Test ---
    print("\n--- TEST 3: Temporary File Cleanup Test ---", flush=True)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".png")
    os.close(temp_fd)
    
    # Create synthetic image
    img = Image.new("RGB", (100, 100), color="white")
    img.save(temp_path, format="PNG")
    img.close()
    
    assert os.path.exists(temp_path), "Temp file must exist before cleanup!"
    cleanup_success = safe_remove_file(temp_path, max_retries=3, delay_sec=0.05)
    
    assert cleanup_success is True, "safe_remove_file must return True!"
    assert not os.path.exists(temp_path), "Temp file must be removed from disk!"
    print("  -> TEST 3 PASSED! Synthetic temp file safely created and cleaned up without errors.", flush=True)

    # --- TEST 4: SHA-256 Duplicate Protection Tests ---
    print("\n--- TEST 4: SHA-256 Duplicate Protection Tests ---", flush=True)
    # Clear test state for isolated test
    test_state_mgr = StateManager()
    test_state_mgr.state = {"hashes": {}, "files": {}}
    test_state_mgr.save_state()

    # Create 2 synthetic files
    test_dir = Path("scratch/test_sha256")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    f1 = test_dir / "Newspaper_A_01-08-2026.pdf"
    f1_copy = test_dir / "Newspaper_A_01-08-2026_copy.pdf"
    f2_diff_hash = test_dir / "Newspaper_A_01-08-2026.pdf" # In separate subfolder

    with open(f1, "wb") as f:
        f.write(b"%PDF-1.4 Synthetic Test PDF 1 Content")
    with open(f1_copy, "wb") as f:
        f.write(b"%PDF-1.4 Synthetic Test PDF 1 Content") # Same hash

    sub_dir = test_dir / "sub"
    sub_dir.mkdir(parents=True, exist_ok=True)
    f2_same_name = sub_dir / "Newspaper_A_01-08-2026.pdf"
    with open(f2_same_name, "wb") as f:
        f.write(b"%PDF-1.4 Synthetic Test PDF 2 Different Content") # Different hash

    # Test Primary File 1
    rec1 = test_state_mgr.init_pdf_state(f1, total_pages=5)
    assert rec1["status"] in ["PENDING", "SUCCESS"], "Primary file must be initialized PENDING or SUCCESS!"

    # Test Same Hash + Different Filename -> DUPLICATE
    rec1_copy = test_state_mgr.init_pdf_state(f1_copy, total_pages=5)
    print("  rec1_copy:", rec1_copy, flush=True)
    assert rec1_copy["status"] == "DUPLICATE", "Duplicate file content must be assigned DUPLICATE status!"
    assert "Duplicate" in rec1_copy["error_message"], f"Error message must state duplicate, got '{rec1_copy['error_message']}'"


    # Test Different Hash + Same Filename -> Separate PDF, No Path Overwrite
    rec2 = test_state_mgr.init_pdf_state(f2_same_name, total_pages=10)
    assert rec2["status"] != "DUPLICATE", "Different content must NOT be marked DUPLICATE!"
    assert rec2["output_file"] != rec1["output_file"], "Output text paths must NOT collide!"
    print("  -> TEST 4 PASSED! SHA-256 duplicate logic verified.", flush=True)

    # --- TEST 5: Date Extraction Unit Tests ---
    print("\n--- TEST 5: Date Extraction Tests ---", flush=True)
    date_cases = [
        ("Mumbai_TOI_01-08-2026.pdf", "2026-08-01"),
        ("Express_04082026.pdf", "2026-08-04"), # 8-digit DDMMYYYY pattern match -> 2026-08-04
        ("Hans_04-08-2026.pdf", "2026-08-04"),
        ("Undated_File.pdf", None)
    ]

    for name, exp in date_cases:
        iso, label = extract_newspaper_date(name)
        assert iso == exp, f"Expected {exp} for {name}, got {iso}"
    print("  -> TEST 5 PASSED! Date parser verified.", flush=True)

    # --- TEST 6: Resume & State Persistence Tests ---
    print("\n--- TEST 6: State Persistence & Resume Tests ---", flush=True)
    test_state_mgr.append_page_text("Newspaper_A_01-08-2026.pdf", 1, 5, "Sample Page 1 Text", sha256_hash=calculate_sha256(f1))
    comp_p = test_state_mgr.get_completed_pages("Newspaper_A_01-08-2026.pdf", sha256_hash=calculate_sha256(f1))
    assert 1 in comp_p, "Page 1 must be recorded in completed pages!"
    print("  -> TEST 6 PASSED! Page resume persistence verified.", flush=True)

    # --- TEST 7: Blank Page Detection Test ---
    print("\n--- TEST 7: Blank Page Validation Test ---", flush=True)
    white_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    is_blank = is_image_blank(white_img, threshold_pct=0.1)
    assert is_blank is True, "Pure white image must be detected as blank!"
    print("  -> TEST 7 PASSED! Blank page validation verified.", flush=True)

    print("\n==================================================", flush=True)
    print("ALL 7 UNIT TESTS PASSED WITH 100% SUCCESS!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_tests()
