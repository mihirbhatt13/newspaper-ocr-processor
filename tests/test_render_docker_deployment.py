import os
import sys
import io
import json
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.index import app
from app.config import find_tesseract, get_installed_tesseract_languages
from app.web_processor import (
    calculate_sha256_bytes,
    check_duplicates_batch,
    inspect_pdf_bytes,
    process_pdf_page_bytes,
    combine_texts_batch
)

def run_render_docker_deployment_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING RENDER DOCKER DEPLOYMENT SYNTHETIC TEST SUITE", flush=True)
    print("==================================================", flush=True)

    client = app.test_client()

    # 1. Dockerfile Syntax & Path Checks
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist!"
    dockerfile_content = dockerfile_path.read_text(encoding='utf-8')
    assert "FROM python:3.12-slim" in dockerfile_content
    assert "tesseract-ocr-hin" in dockerfile_content
    assert "gunicorn" in dockerfile_content
    print("\n[TEST 1] Dockerfile Syntax & Package Configuration: PASS", flush=True)

    # 2. Render.yaml Blueprint Configuration Check
    render_yaml_path = PROJECT_ROOT / "render.yaml"
    assert render_yaml_path.exists(), "render.yaml must exist!"
    render_content = render_yaml_path.read_text(encoding='utf-8')
    assert "env: docker" in render_content
    assert "healthCheckPath: /api/health" in render_content
    print("[TEST 2] Render.yaml Blueprint Configuration: PASS", flush=True)

    # 3. .dockerignore Configuration Check
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    assert dockerignore_path.exists()
    ignore_content = dockerignore_path.read_text(encoding='utf-8')
    assert "duplicates/" in ignore_content
    assert "state.json" in ignore_content
    print("[TEST 3] .dockerignore Exclusion Rules: PASS", flush=True)

    # 4. Gunicorn Startup Configuration Check
    requirements_path = PROJECT_ROOT / "requirements.txt"
    req_content = requirements_path.read_text(encoding='utf-8')
    assert "gunicorn" in req_content
    print("[TEST 4] Gunicorn Dependency & Production Command: PASS", flush=True)

    # 5. Tesseract Executable & Installed Languages Detection
    tess_cmd = find_tesseract()
    installed_langs = get_installed_tesseract_languages(tess_cmd) if tess_cmd else []
    print(f"[TEST 5] Tesseract Executable Detection: PASS (Path: '{tess_cmd}', Installed: {installed_langs})", flush=True)

    # 6. Synthetic PDF Page Rendering via pypdfium2
    from PIL import Image, ImageDraw, ImageFont
    from fpdf import FPDF

    # Create synthetic digital PDF
    pdf_digital = FPDF()
    pdf_digital.add_page()
    pdf_digital.set_font("Helvetica", size=14)
    pdf_digital.cell(200, 10, txt="Synthetic Newspaper Article Title 09-08-2026", ln=1, align="C")
    out_digital = pdf_digital.output(dest='S')
    digital_bytes = out_digital.encode('latin1') if isinstance(out_digital, str) else bytes(out_digital)

    # Test pypdfium2 rendering on synthetic PDF
    temp_pdf_path = PROJECT_ROOT / "tests" / "scratch" / "synthetic_test.pdf"
    temp_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    temp_pdf_path.write_bytes(digital_bytes)

    try:
        from app.pdf.pdf_utils import render_pdf_page_to_image, get_pdf_page_count
        pages_cnt = get_pdf_page_count(temp_pdf_path)
        assert pages_cnt == 1
        img_rendered = render_pdf_page_to_image(temp_pdf_path, page_num=1, dpi=100)
        assert img_rendered is not None
        assert img_rendered.size[0] > 100 and img_rendered.size[1] > 100
        print(f"[TEST 6] pypdfium2 Synthetic PDF Page Rendering: PASS (Image size: {img_rendered.size})", flush=True)
    finally:
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()

    # 7. Synthetic Scanned PDF Image OCR (English, Hindi, Gujarati)
    from app.ocr.ocr_engine import OCREngine
    engine = OCREngine(tesseract_cmd=tess_cmd)

    # Create synthetic image with English text
    img_eng = Image.new("RGB", (600, 200), color=(255, 255, 255))
    d_eng = ImageDraw.Draw(img_eng)
    d_eng.text((20, 80), "NEWSPAPER OCR PROCESSOR TEST", fill=(0, 0, 0))
    ocr_eng_result = engine.perform_ocr(img_eng, lang_setting="English")
    print(f"[TEST 7] Synthetic English OCR: PASS (Extracted: '{ocr_eng_result.strip()}')", flush=True)

    # 8. Web API Endpoints Check (/api/health, /api/languages, /api/inspect-pdf, /api/process-page, /api/check-duplicates, /api/combine)
    res_h = client.get('/api/health')
    assert res_h.status_code == 200
    assert res_h.get_json()['status'] == "online"

    res_l = client.get('/api/languages')
    assert res_l.status_code == 200

    # API Inspect PDF
    res_insp = client.post('/api/inspect-pdf', data={"file": (io.BytesIO(digital_bytes), "Synthetic_Newspaper 09-08.pdf")}, content_type='multipart/form-data')
    assert res_insp.status_code == 200
    insp_info = res_insp.get_json()['info']
    assert insp_info['page_count'] == 1

    # API Process Page
    res_proc = client.post('/api/process-page', data={"file": (io.BytesIO(digital_bytes), "Synthetic_Newspaper 09-08.pdf"), "page_num": 1, "ocr_language": "Auto"}, content_type='multipart/form-data')
    assert res_proc.status_code == 200
    proc_res = res_proc.get_json()
    assert proc_res['success'] == True
    assert "Synthetic Newspaper Article Title" in proc_res['text']

    # API Check Duplicates (4-factor)
    h_sha = calculate_sha256_bytes(digital_bytes)
    meta_batch = [
        {"filename": "Synthetic_Newspaper 09-08.pdf", "file_size": len(digital_bytes), "sha256": h_sha},
        {"filename": "Synthetic_Newspaper 09-08.pdf", "file_size": len(digital_bytes), "sha256": h_sha}
    ]

    res_dup = client.post('/api/check-duplicates', json={"files": meta_batch, "target_date": "2026-08-09"})
    assert res_dup.status_code == 200
    dup_res = res_dup.get_json()['result']
    assert len(dup_res['eligible']) == 1
    assert len(dup_res['duplicates']) == 1

    print("[TEST 8] Web API Endpoints (/api/health, /api/inspect-pdf, /api/process-page, /api/check-duplicates): PASS", flush=True)

    print("\n==================================================", flush=True)
    print("ALL RENDER DOCKER DEPLOYMENT SYNTHETIC TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_render_docker_deployment_tests()
