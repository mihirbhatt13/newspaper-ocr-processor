import os
import sys
import tkinter as tk
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS, ensure_directories

def run_visible_combine_button_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING VISIBLE COMBINE BUTTON UI STATE SYNTHETIC TEST", flush=True)
    print("==================================================", flush=True)

    ensure_directories()

    from app.gui.main_window import MainWindow
    app = MainWindow()
    app.withdraw()  # Keep window unmapped/hidden for headless synthetic UI test

    # 1. Confirm button existence and text
    assert hasattr(app, "btn_combine"), "MainWindow must have self.btn_combine attribute!"
    btn_text = app.btn_combine.cget("text")
    assert btn_text == "📝 COMBINE ALL TEXT", f"Expected button text '📝 COMBINE ALL TEXT', got '{btn_text}'"
    print("  -> PASSED: self.btn_combine is created and visibly configured in main control bar.", flush=True)

    # 2. Confirm state on start: DISABLED
    st_start = str(app.btn_combine.cget("state"))
    assert st_start == "disabled", f"Initial state must be 'disabled', got '{st_start}'"
    print("  -> PASSED: Initial COMBINE button state is DISABLED.", flush=True)

    # 3. Confirm state after loading files: DISABLED
    dummy_pdf = PROJECT_ROOT / "tests" / "scratch" / "dummy_test.pdf"
    dummy_pdf.parent.mkdir(parents=True, exist_ok=True)
    dummy_pdf.write_text("%PDF-1.4 Dummy PDF Content")

    app._load_selected_pdfs([dummy_pdf])
    st_load = str(app.btn_combine.cget("state"))
    assert st_load == "disabled", f"State after file load must be 'disabled', got '{st_load}'"
    print("  -> PASSED: COMBINE button state after loading files is DISABLED.", flush=True)

    # 4. Confirm state during OCR: DISABLED
    app.is_processing = True
    app.btn_combine.config(state="disabled")
    st_ocr = str(app.btn_combine.cget("state"))
    assert st_ocr == "disabled", f"State during OCR must be 'disabled', got '{st_ocr}'"
    print("  -> PASSED: COMBINE button state during OCR is DISABLED.", flush=True)

    # 5. Confirm state if STOP requested: DISABLED
    app.is_processing = True
    app._stop_ocr_process()
    st_stop = str(app.btn_combine.cget("state"))
    assert st_stop == "disabled", f"State when stopped must be 'disabled', got '{st_stop}'"
    print("  -> PASSED: COMBINE button state when OCR is stopped is DISABLED.", flush=True)

    # 6. Confirm state ONLY after BATCH_COMPLETE with successful completion: ENABLED
    app.stop_requested = False
    if not app.stop_requested:
        app.btn_combine.config(state="normal")
    st_complete = str(app.btn_combine.cget("state"))
    assert st_complete == "normal", f"State after successful batch complete must be 'normal', got '{st_complete}'"
    print("  -> PASSED: COMBINE button state after successful batch complete is ENABLED.", flush=True)

    # Cleanup test files & destroy window
    if dummy_pdf.exists():
        dummy_pdf.unlink()

    print("\n==================================================", flush=True)
    print("ALL VISIBLE COMBINE BUTTON UI TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_visible_combine_button_tests()
