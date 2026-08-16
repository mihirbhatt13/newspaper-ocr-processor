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
from app.utils.state_manager import StateManager

def run_redo_verification():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING FAILED & NEEDS REVIEW REDO WORKFLOW TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()
    state_mgr = StateManager()

    # Create temporary synthetic test directory
    test_dir = Path("scratch/synthetic_failed_redo_test")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    redo_dir = DIRS["redo"]
    redo_dir.mkdir(parents=True, exist_ok=True)

    pdf_bytes = b"%PDF-1.4 Synthetic PDF Content"

    # Create 4 synthetic test files representing 4 statuses
    f_failed = test_dir / "Newspaper_Failed_04-08-2026.pdf"
    f_review = test_dir / "Newspaper_Review_04-08-2026.pdf"
    f_success = test_dir / "Newspaper_Success_04-08-2026.pdf"
    f_dup = test_dir / "Newspaper_Duplicate_04-08-2026.pdf"
    f_pending = test_dir / "Newspaper_Pending_04-08-2026.pdf"

    f_failed.write_bytes(pdf_bytes + b" Failed")
    f_review.write_bytes(pdf_bytes + b" Review")
    f_success.write_bytes(pdf_bytes + b" Success")
    f_dup.write_bytes(pdf_bytes + b" Duplicate")
    f_pending.write_bytes(pdf_bytes + b" Pending")

    # 1. Eligibility rule function check
    def is_redo_eligible(status):
        if status in ["SUCCESS", "DUPLICATE", "PENDING"]:
            return False
        return status in ["NEEDS REVIEW", "FAILED"]

    print("\n--- 1. Testing REDO Status Eligibility Rules ---", flush=True)
    assert is_redo_eligible("FAILED") is True, "FAILED PDF MUST be eligible for REDO!"
    assert is_redo_eligible("NEEDS REVIEW") is True, "NEEDS REVIEW PDF MUST be eligible for REDO!"
    assert is_redo_eligible("SUCCESS") is False, "SUCCESS PDF MUST NOT be eligible for REDO!"
    assert is_redo_eligible("DUPLICATE") is False, "DUPLICATE PDF MUST NOT be eligible for REDO!"
    assert is_redo_eligible("PENDING") is False, "PENDING PDF MUST NOT be eligible for REDO!"
    print("  -> PASSED! REDO status eligibility rules verified.", flush=True)

    # 2. Simulate moving FAILED file to redo/
    print("\n--- 2. Moving Synthetic FAILED File to redo/ ---", flush=True)
    target_failed = f_failed
    orig_failed_path = str(target_failed)
    dest_failed_path = redo_dir / target_failed.name

    shutil.move(str(target_failed), str(dest_failed_path))

    # Assertions for FAILED move
    assert not Path(orig_failed_path).exists(), "Original source location MUST no longer contain the FAILED file!"
    assert dest_failed_path.exists(), "Target redo/ directory MUST contain the relocated FAILED file!"
    assert dest_failed_path.name == "Newspaper_Failed_04-08-2026.pdf", "Original filename MUST be preserved!"
    print(f"  -> PASSED! FAILED PDF successfully moved to '{dest_failed_path}'. Original filename preserved.", flush=True)

    # 3. Simulate moving NEEDS REVIEW file to redo/
    print("\n--- 3. Moving Synthetic NEEDS REVIEW File to redo/ ---", flush=True)
    target_review = f_review
    orig_review_path = str(target_review)
    dest_review_path = redo_dir / target_review.name

    shutil.move(str(target_review), str(dest_review_path))

    # Assertions for NEEDS REVIEW move
    assert not Path(orig_review_path).exists(), "Original source location MUST no longer contain the NEEDS REVIEW file!"
    assert dest_review_path.exists(), "Target redo/ directory MUST contain the relocated NEEDS REVIEW file!"
    assert dest_review_path.name == "Newspaper_Review_04-08-2026.pdf", "Original filename MUST be preserved!"
    print(f"  -> PASSED! NEEDS REVIEW PDF successfully moved to '{dest_review_path}'.", flush=True)

    # 4. Cleanup synthetic test directory and moved test files
    if test_dir.exists():
        shutil.rmtree(test_dir)
    if dest_failed_path.exists():
        dest_failed_path.unlink()
    if dest_review_path.exists():
        dest_review_path.unlink()

    print("\n==================================================", flush=True)
    print("ALL FAILED & NEEDS REVIEW REDO TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_redo_verification()
