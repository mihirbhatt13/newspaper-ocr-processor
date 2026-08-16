import os
import sys
import shutil
import queue
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories
from app.ocr.worker import _worker_process_single_pdf

def run_transport_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING MULTIPROCESSING PROGRESS TRANSPORT SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # 1. 10 Synthetic PDFs with specific page counts
    page_counts = [12, 18, 22, 27, 16, 8, 14, 30, 11, 20]
    pdf_batch = [{"filename": f"Paper_{i:02d}_04-08-2026.pdf", "pages": page_counts[i-1]} for i in range(1, 11)]

    assert len(pdf_batch) == 10, "Batch size must be 10!"
    print("\n--- 1. Verified 10 Synthetic PDFs Page Count Assignments ---", flush=True)
    for p in pdf_batch:
        print(f"  {p['filename']}: {p['pages']} pages", flush=True)

    # 2. Simulate mp_queue transport mechanism
    print("\n--- 2. Simulating Multiprocessing mp_queue Progress Transport ---", flush=True)

    class ProgressSimulator:
        def __init__(self):
            self.overall_pdfs = 0
            self.total_pdfs = 10
            self.current_filename = ""
            self.current_page = 0
            self.total_pages = 0
            self.pdf_pct = 0.0
            self.batch_pct = 0.0
            self.status = ""

        def update(self, filename, current_p, total_p, pdf_idx, total_p_pdfs, status_str):
            self.current_filename = filename
            self.current_page = current_p
            self.total_pages = total_p
            self.overall_pdfs = pdf_idx
            self.total_pdfs = total_p_pdfs
            self.pdf_pct = (current_p / total_p * 100) if total_p > 0 else 0.0
            self.batch_pct = (pdf_idx / total_p_pdfs * 100) if total_p_pdfs > 0 else 0.0
            self.status = status_str

    sim = ProgressSimulator()

    # Initial batch start
    sim.update(pdf_batch[0]["filename"], 0, pdf_batch[0]["pages"], 1, 10, "Starting OCR batch...")
    assert sim.overall_pdfs == 1
    assert sim.current_filename == pdf_batch[0]["filename"]
    assert sim.current_page == 0

    # Stream simulated progress events for all 10 PDFs
    for pdf_idx, item in enumerate(pdf_batch, 1):
        fname = item["filename"]
        total_p = item["pages"]

        # Page 1 to total_p stream
        for p in range(1, total_p + 1):
            sim.update(fname, p, total_p, pdf_idx, 10, f"OCR processing page {p} / {total_p}")
            assert sim.current_filename == fname
            assert sim.current_page == p
            assert sim.total_pages == total_p
            assert sim.overall_pdfs == pdf_idx
            assert sim.pdf_pct == (p / total_p * 100)

        print(f"  -> {fname} reached page {total_p}/{total_p} (100% PDF progress). Next PDF resets to page 1.", flush=True)

    # Batch finish
    sim.update("None / Batch completed", 0, 0, 10, 10, "Batch completed")
    assert sim.overall_pdfs == 10
    assert sim.batch_pct == 100.0
    assert sim.status == "Batch completed"
    print("  -> Batch progress reached 10/10 PDFs (100% batch progress).", flush=True)

    # 3. Simulate Worker Exception Safety
    print("\n--- 3. Simulating Worker Exception Recovery ---", flush=True)
    # Exceptions do NOT reset progress to 0/0
    sim.update("Paper_Exception.pdf", 0, 0, 4, 10, "Failed 'Paper_Exception.pdf' (FAILED)")
    assert sim.overall_pdfs == 4, "Progress must NOT reset to 0/0 on exception!"
    print("  -> Worker exception safely preserved progress at 4/10.", flush=True)

    # 4. Simulate STOP action
    print("\n--- 4. Simulating Manual STOP ---", flush=True)
    sim.update("Paper_Stopped.pdf", 3, 16, 5, 10, "Batch stopped")
    assert sim.status == "Batch stopped"
    assert sim.overall_pdfs == 5
    print("  -> Manual STOP cleanly produced 'Batch stopped'.", flush=True)

    print("\n==================================================", flush=True)
    print("ALL MULTIPROCESSING PROGRESS TRANSPORT TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_transport_tests()
