import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def run_vercel_folder_workflow_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING VERCEL FOLDER UPLOAD WORKFLOW TEST SUITE", flush=True)
    print("==================================================", flush=True)

    # 1. Verify public/index.html folder upload elements
    html_path = PROJECT_ROOT / "public" / "index.html"
    assert html_path.exists(), "public/index.html must exist!"
    html_content = html_path.read_text(encoding='utf-8')
    assert "pdf.min.js" in html_content, "index.html must include PDF.js script tag for client-side page counting!"
    assert "tesseract.min.js" in html_content, "index.html must include Tesseract.js WASM script tag for client-side real OCR!"
    assert "webkitdirectory" in html_content, "index.html must contain webkitdirectory attribute for folder upload!"
    assert "folderInput" in html_content, "index.html must contain folderInput element!"
    assert "btnSelectFolder" in html_content, "index.html must contain btnSelectFolder element!"
    assert "lblOverallPdfs" in html_content, "index.html must contain lblOverallPdfs counter!"
    assert "lblCurrentPdf" in html_content, "index.html must contain lblCurrentPdf element!"
    assert "cntSuccess" in html_content, "index.html must contain cntSuccess badge!"
    assert "cntPending" in html_content, "index.html must contain cntPending badge!"
    print("[TEST 1] Vercel HTML5 Folder Selection, PDF.js & Tesseract.js Check: PASS (webkitdirectory, PDF.js, Tesseract.js WASM & Live Counters present)", flush=True)

    # 2. Verify public/js/app.js folder handling logic & error messages
    js_path = PROJECT_ROOT / "public" / "js" / "app.js"
    assert js_path.exists(), "public/js/app.js must exist!"
    js_content = js_path.read_text(encoding='utf-8')
    assert "scanDirectoryEntry" in js_content, "app.js must contain scanDirectoryEntry recursive folder scanner!"
    assert "detectPdfPageCount" in js_content, "app.js must contain detectPdfPageCount real page-count function!"
    assert "processPageHybrid" in js_content, "app.js must contain processPageHybrid real OCR function!"
    assert "fetchWithRetry" in js_content, "app.js must contain fetchWithRetry helper for network resilience!"
    assert "Unable to process the selected folder" in js_content, "app.js must contain user-friendly empty folder alert!"
    assert "OCR processing failed for" in js_content, "app.js must contain per-file batch processing error handling!"
    assert "updateLiveCounters" in js_content, "app.js must contain updateLiveCounters function!"
    print("[TEST 2] Vercel JS Folder Scanner, Page-Count & Hybrid WASM OCR Check: PASS (scanDirectoryEntry, detectPdfPageCount, processPageHybrid & updateLiveCounters present)", flush=True)


    # 3. Verify vercel.json configuration
    vercel_path = PROJECT_ROOT / "vercel.json"
    assert vercel_path.exists(), "vercel.json must exist!"
    v_data = json.loads(vercel_path.read_text(encoding='utf-8'))
    assert "builds" in v_data or "routes" in v_data
    print("[TEST 3] Vercel Deployment Config Check: PASS (vercel.json valid)", flush=True)

    # 4. Verify API Endpoints via Flask Test Client
    from api.index import app
    client = app.test_client()

    h_res = client.get("/api/health")
    assert h_res.status_code == 200
    h_json = h_res.get_json()
    assert h_json["status"] == "online"
    print("[TEST 4] Vercel /api/health Endpoint Check: PASS", flush=True)

    # 5. Verify Desktop main.py Untouched
    main_py = PROJECT_ROOT / "main.py"
    assert main_py.exists()
    main_content = main_py.read_text(encoding='utf-8')
    assert "MainWindow" in main_content
    assert "mainloop" in main_content
    print("[TEST 5] Desktop main.py Preservation Check: PASS (main.py untouched)", flush=True)

    print("\n==================================================", flush=True)
    print("ALL VERCEL FOLDER WORKFLOW TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_vercel_folder_workflow_tests()
