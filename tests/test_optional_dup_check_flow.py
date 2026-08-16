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

def run_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING OPTIONAL DUPLICATE CHECK CONTROL FLOW SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # Create temporary synthetic test folder
    test_dir = Path("scratch/synthetic_optional_dup_flow_test")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create 5 synthetic PDF files: 3 unique, 2 duplicates
    content_1 = b"%PDF-1.4 Synthetic PDF Doc 1"
    content_2 = b"%PDF-1.4 Synthetic PDF Doc 2"
    content_3 = b"%PDF-1.4 Synthetic PDF Doc 3"

    f1 = test_dir / "Hyderabad_TOI_03-08-2026.pdf"
    f2 = test_dir / "Hyderabad_TOI_03-08-2026_copy.pdf" # Dup of f1
    f3 = test_dir / "Aajtak_04082026.pdf"
    f4 = test_dir / "Aajtak_04082026_dup.pdf" # Dup of f3
    f5 = test_dir / "Andhraprabha_AP_04-08-2026.pdf"

    f1.write_bytes(content_1)
    f2.write_bytes(content_1)
    f3.write_bytes(content_2)
    f4.write_bytes(content_2)
    f5.write_bytes(content_3)

    all_synthetic_pdfs = [f1, f2, f3, f4, f5]

    # Simulating App Control Flow State
    class AppState:
        def __init__(self):
            self.selected_pdfs = []
            self.ocr_queue = []
            self.duplicate_records = []
            self.has_checked_duplicates = False

        def load_folder(self, pdf_list):
            self.selected_pdfs = list(pdf_list)
            self.ocr_queue = list(self.selected_pdfs)
            self.duplicate_records = []
            self.has_checked_duplicates = False

        def check_duplicates(self):
            identity_map = {}
            self.ocr_queue = []
            self.duplicate_records = []
            for pdf in self.selected_pdfs:
                sha = calculate_sha256(pdf)
                title, dt = extract_newspaper_info(pdf.name)
                key = (title, dt, sha)
                if key in identity_map:
                    self.duplicate_records.append({
                        "filename": pdf.name,
                        "newspaper": title,
                        "date": dt,
                        "duplicate_of": identity_map[key][1],
                        "sha256": sha,
                        "status": "DUPLICATE"
                    })
                else:
                    identity_map[key] = (pdf, pdf.name)
                    self.ocr_queue.append(pdf)
            self.has_checked_duplicates = True

        def get_target_ocr_pdfs(self):
            if self.has_checked_duplicates:
                return self.ocr_queue
            return self.selected_pdfs

    app = AppState()

    # Step 1 & 2: Load Folder -> Verify NO automatic duplicate check
    print("\n--- 1. Folder Selection Test ---", flush=True)
    app.load_folder(all_synthetic_pdfs)
    assert not app.has_checked_duplicates, "has_checked_duplicates MUST be False on folder load!"
    assert len(app.selected_pdfs) == 5, f"Expected 5 selected PDFs, got {len(app.selected_pdfs)}"
    assert len(app.duplicate_records) == 0, "duplicate_records MUST be empty on folder load!"
    print("  -> PASSED! Folder loaded without automatic duplicate checking.", flush=True)

    # Step 3 & 4: START OCR in State A (no check duplicates performed) -> Uses ALL 5 PDFs
    print("\n--- 2. START OCR in State A (No Check Duplicates Clicked) ---", flush=True)
    targets_state_a = app.get_target_ocr_pdfs()
    assert len(targets_state_a) == 5, f"Expected ALL 5 PDFs in State A, got {len(targets_state_a)}"
    print("  -> PASSED! START OCR proceeds directly with all 5 selected PDFs without prompting.", flush=True)

    # Step 5, 6, 7: Explicitly click CHECK DUPLICATES -> Identifies 2 duplicates, 3 unique
    print("\n--- 3. Explicit User Click on CHECK DUPLICATES ---", flush=True)
    app.check_duplicates()
    assert app.has_checked_duplicates, "has_checked_duplicates MUST be True after check_duplicates()!"
    assert len(app.duplicate_records) == 2, f"Expected 2 duplicate records, got {len(app.duplicate_records)}"
    assert len(app.ocr_queue) == 3, f"Expected 3 unique PDFs in ocr_queue, got {len(app.ocr_queue)}"
    print("  -> PASSED! Check Duplicates populated 2 duplicate records and 3 unique OCR queue items.", flush=True)

    # Step 8: START OCR in State B (after Check Duplicates) -> Uses ONLY 3 Unique PDFs
    print("\n--- 4. START OCR in State B (After Check Duplicates Clicked) ---", flush=True)
    targets_state_b = app.get_target_ocr_pdfs()
    assert len(targets_state_b) == 3, f"Expected 3 UNIQUE PDFs in State B, got {len(targets_state_b)}"
    assert f2 not in targets_state_b and f4 not in targets_state_b, "Duplicates MUST be excluded from OCR queue in State B!"
    print("  -> PASSED! START OCR processes ONLY 3 unique PDFs, excluding duplicates.", flush=True)

    # Step 9 & 10: Load NEW folder -> Resets state, does NOT auto check duplicates
    print("\n--- 5. Loading NEW Folder (State Reset Test) ---", flush=True)
    new_folder_pdfs = [f1, f3, f5]
    app.load_folder(new_folder_pdfs)
    assert not app.has_checked_duplicates, "has_checked_duplicates MUST reset to False when new folder is loaded!"
    assert len(app.selected_pdfs) == 3, f"Expected 3 selected PDFs in new folder, got {len(app.selected_pdfs)}"
    assert len(app.duplicate_records) == 0, "duplicate_records MUST reset to empty on new folder load!"
    
    targets_new_state_a = app.get_target_ocr_pdfs()
    assert len(targets_new_state_a) == 3, f"Expected all 3 PDFs in new folder State A, got {len(targets_new_state_a)}"
    print("  -> PASSED! New folder selection cleanly resets duplicate state and allows direct OCR.", flush=True)

    # Cleanup synthetic test folder
    if test_dir.exists():
        shutil.rmtree(test_dir)

    print("\n==================================================", flush=True)
    print("ALL OPTIONAL DUPLICATE CHECK CONTROL FLOW TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_tests()
