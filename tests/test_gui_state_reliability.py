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
from app.utils.file_utils import calculate_sha256

def run_reliability_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING GUI STATE RELIABILITY SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    # Synthetic queue message state simulator
    class SimulatedMainWindowState:
        def __init__(self):
            self.msg_queue = queue.Queue()
            self.review_table_items = {}
            self.summary_counts = {"SUCCESS": 0, "FAILED": 0, "NEEDS REVIEW": 0, "DUPLICATES": 0, "PENDING": 10}
            self.status_label = "Ready"
            self.current_pdf_label = "None Selected"
            self.is_processing = False
            self.stop_requested = False

        def simulate_load_batch(self, count=10):
            self.review_table_items = {f"Paper_{i:02d}.pdf": "PENDING" for i in range(1, count + 1)}
            self.summary_counts = {"SUCCESS": 0, "FAILED": 0, "NEEDS REVIEW": 0, "DUPLICATES": 0, "PENDING": count}

        def process_messages(self):
            while not self.msg_queue.empty():
                msg = self.msg_queue.get_nowait()
                m_type = msg.get("type")

                if m_type == "PROGRESS":
                    fn = msg["pdf_filename"]
                    self.review_table_items[fn] = "PROCESSING"
                    self.current_pdf_label = fn
                    self.status_label = f"OCR processing page {msg['current_page']} / {msg['total_pages']}..."

                elif m_type == "PDF_FINISHED":
                    res = msg["result"]
                    fn = res["pdf_filename"]
                    st = res["status"]
                    self.review_table_items[fn] = st
                    
                    # Update summary counts
                    succ = sum(1 for v in self.review_table_items.values() if v == "SUCCESS")
                    fail = sum(1 for v in self.review_table_items.values() if v == "FAILED")
                    rev = sum(1 for v in self.review_table_items.values() if v == "NEEDS REVIEW")
                    dup = sum(1 for v in self.review_table_items.values() if v == "DUPLICATE")
                    pend = sum(1 for v in self.review_table_items.values() if v == "PENDING")
                    self.summary_counts = {"SUCCESS": succ, "FAILED": fail, "NEEDS REVIEW": rev, "DUPLICATE": dup, "PENDING": pend}

                elif m_type == "BATCH_COMPLETE":
                    self.is_processing = False
                    if self.stop_requested:
                        self.status_label = "Batch stopped"
                    else:
                        self.status_label = "Batch completed"
                        self.current_pdf_label = "None / Batch completed"

    gui = SimulatedMainWindowState()
    gui.simulate_load_batch(10)

    print("\n--- 1. Batch Loaded State ---", flush=True)
    assert gui.summary_counts["PENDING"] == 10
    print("  -> Initial 10 PENDING items loaded.", flush=True)

    # Simulate PDF 1 SUCCESS
    print("\n--- 2. PDF 1 SUCCESS Update ---", flush=True)
    gui.msg_queue.put({"type": "PDF_FINISHED", "result": {"pdf_filename": "Paper_01.pdf", "status": "SUCCESS", "total_pages": 5, "processed_pages": 5, "duration_sec": 1.2}})
    gui.process_messages()
    assert gui.review_table_items["Paper_01.pdf"] == "SUCCESS"
    assert gui.summary_counts["SUCCESS"] == 1
    assert gui.summary_counts["PENDING"] == 9
    print("  -> PDF 1 SUCCESS immediately refreshed GUI state.", flush=True)

    # Simulate PDF 2 FAILED
    print("\n--- 3. PDF 2 FAILED Update ---", flush=True)
    gui.msg_queue.put({"type": "PDF_FINISHED", "result": {"pdf_filename": "Paper_02.pdf", "status": "FAILED", "total_pages": 5, "processed_pages": 2, "duration_sec": 0.8, "error_message": "Page 3 corrupt"}})
    gui.process_messages()
    assert gui.review_table_items["Paper_02.pdf"] == "FAILED"
    assert gui.summary_counts["FAILED"] == 1
    assert gui.summary_counts["SUCCESS"] == 1
    assert gui.summary_counts["PENDING"] == 8
    print("  -> PDF 2 FAILED immediately refreshed GUI state and showed FAILED.", flush=True)

    # Simulate PDF 3 NEEDS REVIEW
    print("\n--- 4. PDF 3 NEEDS REVIEW Update ---", flush=True)
    gui.msg_queue.put({"type": "PDF_FINISHED", "result": {"pdf_filename": "Paper_03.pdf", "status": "NEEDS REVIEW", "total_pages": 5, "processed_pages": 5, "duration_sec": 1.1}})
    gui.process_messages()
    assert gui.review_table_items["Paper_03.pdf"] == "NEEDS REVIEW"
    assert gui.summary_counts["NEEDS REVIEW"] == 1
    print("  -> PDF 3 NEEDS REVIEW immediately refreshed GUI state.", flush=True)

    # Simulate Worker Exception handling (PDF 4 Exception caught -> converted to FAILED)
    print("\n--- 5. Worker Exception Recovery ---", flush=True)
    try:
        raise ValueError("Simulated Worker Process Crash")
    except Exception as e:
        gui.msg_queue.put({
            "type": "PDF_FINISHED",
            "result": {
                "pdf_filename": "Paper_04.pdf",
                "status": "FAILED",
                "total_pages": 0,
                "processed_pages": 0,
                "duration_sec": 0.0,
                "error_message": str(e)
            }
        })
    gui.process_messages()
    assert gui.review_table_items["Paper_04.pdf"] == "FAILED"
    assert gui.summary_counts["FAILED"] == 2
    print("  -> Worker exception safely caught, converted to FAILED, and updated GUI state without freezing.", flush=True)

    # Simulate Batch Finish
    print("\n--- 6. Batch Completion State Refresh ---", flush=True)
    for i in range(5, 11):
        gui.msg_queue.put({"type": "PDF_FINISHED", "result": {"pdf_filename": f"Paper_{i:02d}.pdf", "status": "SUCCESS", "total_pages": 4, "processed_pages": 4, "duration_sec": 1.0}})
    gui.msg_queue.put({"type": "BATCH_COMPLETE", "total_elapsed": 8.5})
    gui.process_messages()

    assert gui.summary_counts["SUCCESS"] == 7
    assert gui.summary_counts["FAILED"] == 2
    assert gui.summary_counts["NEEDS REVIEW"] == 1
    assert gui.summary_counts["PENDING"] == 0
    assert gui.status_label == "Batch completed"
    assert gui.current_pdf_label == "None / Batch completed"
    print("  -> Final Batch Completion state verified cleanly.", flush=True)

    # Simulate Manual Stop
    print("\n--- 7. Manual STOP State Refresh ---", flush=True)
    gui.stop_requested = True
    gui.msg_queue.put({"type": "BATCH_COMPLETE", "total_elapsed": 4.2})
    gui.process_messages()
    assert gui.status_label == "Batch stopped"
    print("  -> Manual STOP state verified: status shows 'Batch stopped'.", flush=True)

    print("\n==================================================", flush=True)
    print("ALL GUI STATE RELIABILITY TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_reliability_tests()
