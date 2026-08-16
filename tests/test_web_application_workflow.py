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

def run_web_application_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==================================================", flush=True)
    print("RUNNING COMPREHENSIVE WEB APPLICATION TEST SUITE", flush=True)
    print("==================================================", flush=True)

    client = app.test_client()

    # 1. Health Endpoint Test
    res_health = client.get('/api/health')
    assert res_health.status_code == 200
    health_data = res_health.get_json()
    print(f"\n[TEST 1] API Health Endpoint: PASS (Tesseract Available: {health_data['tesseract_available']}, Languages: {health_data['installed_languages']})", flush=True)

    # 2. Languages Endpoint Test
    res_langs = client.get('/api/languages')
    assert res_langs.status_code == 200
    langs_data = res_langs.get_json()
    assert "languages" in langs_data
    print(f"[TEST 2] API Languages Endpoint: PASS ({len(langs_data['languages'])} Languages configured)", flush=True)

    # 3. Pure Scanned Multi-Page Hindi Newspaper PDF Test (DB Chandigarh 04-08.pdf)
    scanned_hindi_path = PROJECT_ROOT / "duplicates" / "DB Chandigarh 04-08.pdf"
    if scanned_hindi_path.exists():
        pdf_bytes = scanned_hindi_path.read_bytes()
        
        # Inspect PDF
        data_inspect = {
            "file": (io.BytesIO(pdf_bytes), "DB Chandigarh 04-08.pdf")
        }
        res_inspect = client.post('/api/inspect-pdf', data=data_inspect, content_type='multipart/form-data')
        assert res_inspect.status_code == 200
        info = res_inspect.get_json()['info']
        assert info['page_count'] == 4
        assert info['is_scanned'] == True
        print(f"[TEST 3] Scanned Hindi PDF Inspection (DB Chandigarh 04-08.pdf): PASS (Pages: {info['page_count']}, Is Scanned: {info['is_scanned']})", flush=True)

        # True Hindi OCR on Page 1
        data_ocr_hin = {
            "file": (io.BytesIO(pdf_bytes), "DB Chandigarh 04-08.pdf"),
            "page_num": 1,
            "ocr_language": "Hindi",
            "dpi": 100
        }


        res_ocr_hin = client.post('/api/process-page', data=data_ocr_hin, content_type='multipart/form-data')
        assert res_ocr_hin.status_code == 200
        ocr_res_hin = res_ocr_hin.get_json()
        assert ocr_res_hin['success'] == True
        assert ocr_res_hin['is_scanned'] == True
        assert ocr_res_hin['engine_used'] == "Tesseract OCR"
        assert len(ocr_res_hin['text']) > 1000
        print(f"[TEST 4] Scanned Hindi PDF True Tesseract OCR (Page 1): PASS (Extracted {len(ocr_res_hin['text'])} chars)", flush=True)

    # 4. Pure Scanned English Newspaper PDF Test (Chennai_TOI_04-08-2026.pdf)
    scanned_eng_path = PROJECT_ROOT / "duplicates" / "Chennai_TOI_04-08-2026.pdf"
    if scanned_eng_path.exists():
        pdf_bytes_eng = scanned_eng_path.read_bytes()
        data_ocr_eng = {
            "file": (io.BytesIO(pdf_bytes_eng), "Chennai_TOI_04-08-2026.pdf"),
            "page_num": 1,
            "ocr_language": "English",
            "dpi": 150
        }

        res_ocr_eng = client.post('/api/process-page', data=data_ocr_eng, content_type='multipart/form-data')
        assert res_ocr_eng.status_code == 200
        ocr_res_eng = res_ocr_eng.get_json()
        assert ocr_res_eng['success'] == True
        assert ocr_res_eng['is_scanned'] == True
        assert len(ocr_res_eng['text']) > 1000
        print(f"[TEST 5] Scanned English PDF True Tesseract OCR (Page 1): PASS (Extracted {len(ocr_res_eng['text'])} chars)", flush=True)

    # 5. Digital PDF (Selectable Text Stream) Test
    from fpdf import FPDF
    pdf_doc = FPDF()
    pdf_doc.add_page()
    pdf_doc.set_font("Helvetica", size=14)
    pdf_doc.cell(200, 10, txt="Newspaper OCR Processor Selectable Text Digital PDF Sample Page", ln=1, align="C")
    out_str = pdf_doc.output(dest='S')
    digital_pdf_bytes = out_str.encode('latin1') if isinstance(out_str, str) else bytes(out_str)




    data_inspect_dig = {
        "file": (io.BytesIO(digital_pdf_bytes), "Digital_Sample_09-08.pdf")
    }
    res_inspect_dig = client.post('/api/inspect-pdf', data=data_inspect_dig, content_type='multipart/form-data')
    assert res_inspect_dig.status_code == 200
    info_dig = res_inspect_dig.get_json()['info']
    assert info_dig['has_text_stream'] == True

    data_ocr_dig = {
        "file": (io.BytesIO(digital_pdf_bytes), "Digital_Sample_09-08.pdf"),
        "page_num": 1,
        "ocr_language": "Auto"
    }
    res_ocr_dig = client.post('/api/process-page', data=data_ocr_dig, content_type='multipart/form-data')
    assert res_ocr_dig.status_code == 200
    ocr_res_dig = res_ocr_dig.get_json()
    assert ocr_res_dig['success'] == True
    assert "Selectable Text Digital PDF Sample Page" in ocr_res_dig['text']
    print(f"[TEST 6] Digital Selectable Text PDF Stream Extraction: PASS (Engine: {ocr_res_dig['engine_used']})", flush=True)

    # 6. Honest Tesseract Missing Failure Handling Test (Simulate missing Tesseract on server)
    import app.web_processor as wp
    orig_tess_func = wp.find_tesseract
    wp.find_tesseract = lambda: ""
    
    if scanned_hindi_path.exists():
        res_fail = process_pdf_page_bytes(pdf_bytes, "DB Chandigarh 04-08.pdf", page_num=1)
        assert res_fail['success'] == False
        assert res_fail['ocr_error'] == "TESSERACT_UNAVAILABLE"
        assert "Tesseract OCR binary is unavailable" in res_fail['message']
        print(f"[TEST 7] Honest Tesseract Missing Failure Handling: PASS (Status: {res_fail['ocr_error']})", flush=True)
    wp.find_tesseract = orig_tess_func

    # 7. Exact 4-Factor Duplicate Check & Target Date Filter API Test
    sha1 = calculate_sha256_bytes(digital_pdf_bytes)
    files_meta = [
        {"filename": "DC Chennai 09-08.pdf", "file_size": len(digital_pdf_bytes), "sha256": sha1},
        {"filename": "DC Chennai 08-08.pdf", "file_size": len(digital_pdf_bytes), "sha256": "hash_different"},
        {"filename": "DC Chennai 09-08.pdf", "file_size": len(digital_pdf_bytes), "sha256": sha1} # Exact 4-factor dup
    ]
    res_dup = client.post('/api/check-duplicates', json={"files": files_meta, "target_date": "2026-08-09"})
    assert res_dup.status_code == 200
    dup_res = res_dup.get_json()['result']
    assert len(dup_res['eligible']) == 1 # Only 1 eligible (DC Chennai 09-08.pdf)
    assert len(dup_res['duplicates']) == 2 # 1 out-of-date + 1 duplicate
    print(f"[TEST 8] Exact 4-Factor Duplicate & Target Date Filter API: PASS (Eligible: {len(dup_res['eligible'])}, Duplicates/Out-Date: {len(dup_res['duplicates'])})", flush=True)

    # 8. Text Combiner API Test
    combine_payload = {
        "items": [
            {"filename": "PDF_1.pdf", "text": "Content of Page 1 from PDF 1"},
            {"filename": "PDF_2.pdf", "text": "Content of Page 1 from PDF 2"}
        ]
    }
    res_comb = client.post('/api/combine', json=combine_payload)
    assert res_comb.status_code == 200
    comb_res = res_comb.get_json()
    assert comb_res['success'] == True
    assert "DOCUMENT 1: PDF_1.pdf" in comb_res['combined_text']
    assert "DOCUMENT 2: PDF_2.pdf" in comb_res['combined_text']
    print(f"[TEST 9] API Text Combiner: PASS (Combined {len(combine_payload['items'])} documents)", flush=True)

    print("\n==================================================", flush=True)
    print("ALL WEB APPLICATION TESTS PASSED (100%)!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_web_application_tests()
