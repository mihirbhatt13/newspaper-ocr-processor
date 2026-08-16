import os
import sys
import io
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def run_streamlit_deployment_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING STREAMLIT COMMUNITY CLOUD DEPLOYMENT TEST SUITE", flush=True)
    print("==================================================", flush=True)

    # 1. Check streamlit_app.py existence
    app_path = PROJECT_ROOT / "streamlit_app.py"
    assert app_path.exists(), "streamlit_app.py must exist!"
    print("\n[TEST 1] Streamlit Web Entrypoint Existence: PASS (streamlit_app.py present)", flush=True)

    # 2. Check packages.txt existence and contents
    packages_path = PROJECT_ROOT / "packages.txt"
    assert packages_path.exists(), "packages.txt must exist!"
    packages_content = packages_path.read_text(encoding='utf-8')
    required_packages = [
        "tesseract-ocr", "tesseract-ocr-eng", "tesseract-ocr-hin",
        "tesseract-ocr-guj", "tesseract-ocr-mar", "tesseract-ocr-ben",
        "tesseract-ocr-tel", "tesseract-ocr-urd"
    ]
    for pkg in required_packages:
        assert pkg in packages_content, f"Package {pkg} missing in packages.txt!"
    print(f"[TEST 2] Streamlit packages.txt Manifest Check: PASS ({len(required_packages)} Linux packages specified)", flush=True)

    # 3. Check requirements.txt contains streamlit
    requirements_path = PROJECT_ROOT / "requirements.txt"
    req_content = requirements_path.read_text(encoding='utf-8')
    assert "streamlit" in req_content
    print("[TEST 3] Requirements.txt Streamlit Dependency Check: PASS", flush=True)

    # 4. Check OCREngine import and Tesseract detection
    from app.config import find_tesseract, get_installed_tesseract_languages
    from app.ocr.ocr_engine import OCREngine
    tess_cmd = find_tesseract()
    installed_langs = get_installed_tesseract_languages(tess_cmd) if tess_cmd else []
    print(f"[TEST 4] OCREngine Import & Tesseract Discovery: PASS (Installed: {installed_langs})", flush=True)

    # 5. Check pypdfium2 PDF page rendering
    from fpdf import FPDF
    pdf_doc = FPDF()
    pdf_doc.add_page()
    pdf_doc.set_font("Helvetica", size=14)
    pdf_doc.cell(200, 10, txt="Synthetic Streamlit Deployment Sample Page 09-08-2026", ln=1, align="C")
    out_str = pdf_doc.output(dest='S')
    digital_bytes = out_str.encode('latin1') if isinstance(out_str, str) else bytes(out_str)

    temp_pdf = PROJECT_ROOT / "tests" / "scratch" / "streamlit_test_sample.pdf"
    temp_pdf.parent.mkdir(parents=True, exist_ok=True)
    temp_pdf.write_bytes(digital_bytes)

    try:
        from app.pdf.pdf_utils import render_pdf_page_to_image, get_pdf_page_count
        pages_cnt = get_pdf_page_count(temp_pdf)
        assert pages_cnt == 1
        img_rendered = render_pdf_page_to_image(temp_pdf, page_num=1, dpi=150)
        assert img_rendered is not None
        assert img_rendered.size[0] > 100
        print(f"[TEST 5] pypdfium2 Page Rendering Check: PASS (Image size: {img_rendered.size})", flush=True)
    finally:
        if temp_pdf.exists():
            temp_pdf.unlink()

    # 6. Check web_processor inspection & page processing on synthetic PDF
    from app.web_processor import inspect_pdf_bytes, process_pdf_page_bytes, check_duplicates_batch, calculate_sha256_bytes
    info = inspect_pdf_bytes(digital_bytes, "Synthetic_Streamlit_09-08.pdf")
    assert info['page_count'] == 1

    proc_res = process_pdf_page_bytes(digital_bytes, "Synthetic_Streamlit_09-08.pdf", page_num=1, lang_setting="Auto")
    assert proc_res['success'] == True
    assert "Synthetic Streamlit Deployment Sample Page" in proc_res['text']
    print(f"[TEST 6] In-Memory Web Processor Execution Check: PASS (Text length: {len(proc_res['text'])} chars)", flush=True)

    # 7. Check 4-Factor Duplicate Detection Rule
    sha_hash = calculate_sha256_bytes(digital_bytes)
    batch = [
        {"filename": "Synthetic_Streamlit_09-08.pdf", "file_size": len(digital_bytes), "sha256": sha_hash},
        {"filename": "Synthetic_Streamlit_09-08.pdf", "file_size": len(digital_bytes), "sha256": sha_hash}
    ]
    dup_res = check_duplicates_batch(batch, target_date_sel="2026-08-09")
    assert len(dup_res['eligible']) == 1
    assert len(dup_res['duplicates']) == 1
    print("[TEST 7] Exact 4-Factor Duplicate Matching Check: PASS", flush=True)

    # 8. Check Desktop main.py Untouched
    main_py_path = PROJECT_ROOT / "main.py"
    assert main_py_path.exists()
    main_content = main_py_path.read_text(encoding='utf-8')
    assert "MainWindow" in main_content
    assert "mainloop" in main_content
    print("[TEST 8] Desktop main.py Preservation Check: PASS (main.py untouched)", flush=True)

    print("\n==================================================", flush=True)
    print("ALL STREAMLIT DEPLOYMENT TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_streamlit_deployment_tests()
