import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, request, jsonify, send_from_directory, Response
from app.config import DEFAULT_LANG_MAP, find_tesseract, get_installed_tesseract_languages
from app.web_processor import (
    calculate_sha256_bytes,
    check_duplicates_batch,
    inspect_pdf_bytes,
    process_pdf_page_bytes,
    combine_texts_batch
)

app = Flask(__name__, static_folder="../public", static_url_path="")

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/health", methods=["GET"])
def health():
    backend_url = os.environ.get("OCR_BACKEND_URL")
    tess_cmd = find_tesseract()
    installed_langs = get_installed_tesseract_languages(tess_cmd) if tess_cmd else []
    return jsonify({
        "status": "online",
        "service": "Newspaper OCR Processor Web API",
        "tesseract_available": bool(tess_cmd and os.path.exists(tess_cmd)) or bool(backend_url),
        "tesseract_path": tess_cmd or (f"Remote Proxy: {backend_url}" if backend_url else None),
        "installed_languages": installed_langs,
        "ocr_backend_url": backend_url
    })

@app.route("/api/languages", methods=["GET"])
def get_languages():
    tess_cmd = find_tesseract()
    installed = get_installed_tesseract_languages(tess_cmd) if tess_cmd else []
    
    languages = []
    for display, code in DEFAULT_LANG_MAP.items():
        if display == "Auto":
            languages.append({"name": "Auto (Detect)", "code": "Auto", "installed": True})
        else:
            languages.append({"name": display, "code": code, "installed": code in installed})

    return jsonify({
        "languages": languages,
        "default_lang_map": DEFAULT_LANG_MAP
    })

@app.route("/api/check-duplicates", methods=["POST"])
def api_check_duplicates():
    try:
        data = request.get_json() or {}
        files_metadata = data.get("files", [])
        target_date_sel = data.get("target_date", None)
        
        res = check_duplicates_batch(files_metadata, target_date_sel=target_date_sel)
        return jsonify({"success": True, "result": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/inspect-pdf", methods=["POST"])
def api_inspect_pdf():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No PDF file provided in request."}), 400
        
        f = request.files["file"]
        pdf_bytes = f.read()
        filename = f.filename
        
        info = inspect_pdf_bytes(pdf_bytes, filename)
        info["file_size"] = len(pdf_bytes)
        info["sha256"] = calculate_sha256_bytes(pdf_bytes)
        
        return jsonify({"success": True, "info": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/process-page", methods=["POST"])
def api_process_page():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No PDF file provided in request."}), 400
        
        f = request.files["file"]
        pdf_bytes = f.read()
        filename = f.filename
        
        page_num = int(request.form.get("page_num", 1))
        lang_setting = request.form.get("ocr_language", "Auto")
        dpi = int(request.form.get("dpi", 200))
        
        backend_url = os.environ.get("OCR_BACKEND_URL")
        tess_cmd = find_tesseract()

        # Forward to external OCR backend if configured and local tesseract is unavailable
        if backend_url and not (tess_cmd and os.path.exists(tess_cmd)):
            try:
                import requests as py_requests
                target = f"{backend_url.rstrip('/')}/api/process-page"
                files = {"file": (filename, pdf_bytes, "application/pdf")}
                data = {"page_num": page_num, "ocr_language": lang_setting, "dpi": dpi}
                resp = py_requests.post(target, files=files, data=data, timeout=60)
                return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type", "application/json"))
            except Exception as proxy_err:
                return jsonify({
                    "success": False,
                    "ocr_error": "PROXY_ERROR",
                    "message": f"Failed to reach remote OCR backend service at {backend_url}: {proxy_err}"
                }), 502

        res = process_pdf_page_bytes(pdf_bytes, filename, page_num=page_num, lang_setting=lang_setting, dpi=dpi)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/combine", methods=["POST"])
def api_combine():
    try:
        data = request.get_json() or {}
        items = data.get("items", [])
        
        if not items:
            return jsonify({"success": False, "error": "No items provided for combining."}), 400
        
        combined_text = combine_texts_batch(items)
        return jsonify({"success": True, "combined_text": combined_text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

from app.web_processor import BatchJobManager

@app.route("/api/batch/create", methods=["POST"])
def api_batch_create():
    try:
        backend_url = os.environ.get("OCR_BACKEND_URL")
        tess_cmd = find_tesseract()
        if backend_url and not (tess_cmd and os.path.exists(tess_cmd)):
            import requests as py_requests
            resp = py_requests.post(f"{backend_url.rstrip('/')}/api/batch/create", timeout=30)
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type", "application/json"))

        job_id = BatchJobManager.create_job()
        return jsonify({"success": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/batch/upload-file", methods=["POST"])
def api_batch_upload_file():
    try:
        if "file" not in request.files or "job_id" not in request.form:
            return jsonify({"success": False, "error": "Missing file or job_id in upload request."}), 400
        
        job_id = request.form["job_id"]
        f = request.files["file"]
        filename = f.filename
        pdf_bytes = f.read()

        backend_url = os.environ.get("OCR_BACKEND_URL")
        tess_cmd = find_tesseract()
        if backend_url and not (tess_cmd and os.path.exists(tess_cmd)):
            import requests as py_requests
            files = {"file": (filename, pdf_bytes, "application/pdf")}
            data = {"job_id": job_id}
            resp = py_requests.post(f"{backend_url.rstrip('/')}/api/batch/upload-file", files=files, data=data, timeout=60)
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type", "application/json"))

        res = BatchJobManager.save_file(job_id, filename, pdf_bytes)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/batch/start", methods=["POST"])
def api_batch_start():
    try:
        data = request.get_json() or {}
        job_id = data.get("job_id")
        ocr_language = data.get("ocr_language", "Auto")

        if not job_id:
            return jsonify({"success": False, "error": "Missing job_id."}), 400

        backend_url = os.environ.get("OCR_BACKEND_URL")
        tess_cmd = find_tesseract()
        if backend_url and not (tess_cmd and os.path.exists(tess_cmd)):
            import requests as py_requests
            resp = py_requests.post(f"{backend_url.rstrip('/')}/api/batch/start", json=data, timeout=30)
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type", "application/json"))

        res = BatchJobManager.start_job(job_id, ocr_language=ocr_language)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/batch/status/<job_id>", methods=["GET"])
def api_batch_status(job_id):
    try:
        backend_url = os.environ.get("OCR_BACKEND_URL")
        tess_cmd = find_tesseract()
        if backend_url and not (tess_cmd and os.path.exists(tess_cmd)):
            import requests as py_requests
            resp = py_requests.get(f"{backend_url.rstrip('/')}/api/batch/status/{job_id}", timeout=15)
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type", "application/json"))

        status = BatchJobManager.get_job_status(job_id)
        return jsonify({"success": True, "status_data": status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/batch/result/<job_id>", methods=["GET"])
def api_batch_result(job_id):
    try:
        backend_url = os.environ.get("OCR_BACKEND_URL")
        tess_cmd = find_tesseract()
        if backend_url and not (tess_cmd and os.path.exists(tess_cmd)):
            import requests as py_requests
            resp = py_requests.get(f"{backend_url.rstrip('/')}/api/batch/result/{job_id}", timeout=30)
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type", "application/json"))

        res = BatchJobManager.get_job_result(job_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Catch-all route for static assets
@app.route("/<path:path>")
def static_proxy(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

