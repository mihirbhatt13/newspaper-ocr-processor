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

def run_combine_button_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING MANUAL COMBINE BUTTON & WORKSPACE CLEANUP SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # 1. Empty extracted_text directory test
    print("\n--- 1. Empty extracted_text Case ---", flush=True)
    temp_backup = PROJECT_ROOT / "tests" / "scratch" / "_temp_ext_backup"
    temp_backup.mkdir(parents=True, exist_ok=True)

    backed_up_files = []
    for txt in DIRS["extracted_text"].rglob("*.txt"):
        if txt.is_file() and not txt.name.startswith("all_newspaper"):
            rel_path = txt.relative_to(DIRS["extracted_text"])
            target = temp_backup / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(txt), str(target))
            backed_up_files.append((txt, target))

    success_empty, count_empty, path_empty, msg_empty = combine_all_text_files()
    assert success_empty is False, "Empty directory must return False!"
    assert msg_empty == "NO TEXT FILES AVAILABLE", f"Expected 'NO TEXT FILES AVAILABLE', got '{msg_empty}'"

    assert path_empty == "", "No file path should be created on empty!"
    print("  -> PASSED: Empty extracted_text correctly returned 'NO TEXT FILES TO COMBINE' without creating empty file.", flush=True)

    # Restore backed up TXT files
    for orig, bkp in backed_up_files:
        orig.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(bkp), str(orig))
    shutil.rmtree(temp_backup)

    # 2. Versioned Manual Combine Test (105 files)
    print("\n--- 2. Versioned Combine Test with 105 Synthetic TXT Files ---", flush=True)
    comb_dir = DIRS["combined"]
    comb_dir.mkdir(parents=True, exist_ok=True)

    f1 = comb_dir / "all_newspaper.txt"
    f2 = comb_dir / "all_newspaper2.txt"
    f3 = comb_dir / "all_newspaper3.txt"
    for f in [f1, f2, f3]:
        if f.exists():
            f.unlink()

    # Create 105 synthetic TXT files
    for i in range(1, 106):
        (DIRS["extracted_text"] / f"Synth_News_{i:03d}_07-08-2026.txt").write_text(f"Synthetic content for news paper {i}\n")

    # Click 1: all_newspaper.txt
    s1, c1, p1, m1 = combine_all_text_files()
    assert s1 and Path(p1).name == "all_newspaper.txt"
    assert c1 >= 105

    # Click 2: all_newspaper2.txt
    s2, c2, p2, m2 = combine_all_text_files()
    assert s2 and Path(p2).name == "all_newspaper2.txt"

    # Click 3: all_newspaper3.txt
    s3, c3, p3, m3 = combine_all_text_files()
    assert s3 and Path(p3).name == "all_newspaper3.txt"

    assert f1.exists() and f2.exists() and f3.exists(), "All versioned combined files must exist concurrently without overwrites!"
    print("  -> PASSED: Versioned outputs (all_newspaper.txt, all_newspaper2.txt, all_newspaper3.txt) generated cleanly.", flush=True)

    # Cleanup test files
    for i in range(1, 106):
        p = DIRS["extracted_text"] / f"Synth_News_{i:03d}_07-08-2026.txt"
        if p.exists():
            p.unlink()

    print("\n==================================================", flush=True)
    print("ALL MANUAL COMBINE BUTTON SYNTHETIC TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_combine_button_tests()
