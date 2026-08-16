# Newspaper OCR Processor

A high-performance, multilingual newspaper batch OCR, 4-factor duplicate detection, target-date filtering, and text combining application. Available as both a **Windows Desktop Application** and a **Render Cloud Container Web Application**.

---

## Features & Supported Languages

- **Native Linux & Windows Tesseract OCR Engine**:
  - Full support for English (`eng`), Hindi (`hin`), Gujarati (`guj`), Marathi (`mar`), Bengali (`ben`), Telugu (`tel`), Urdu (`urd`).
  - True scanned-image OCR rendering via `pypdfium2` (pure Python/C++ wheel with no external Poppler binary required).
  - Digital PDF text stream extraction with automatic scanned-page detection.
- **Exact 4-Factor Duplicate Detection**:
  - `Duplicate = (Filename AND File Size AND Extension AND SHA-256 Content Hash)`.
  - If even one factor differs, files are kept as UNIQUE.
- **Target-Date Filtering**:
  - Excludes non-matching newspaper dates (marked `OUT-OF-DATE`).
  - Preserves `DATE UNKNOWN` PDFs.
- **Versioned Text Combining**:
  - Manual `[ 📝 COMBINE ALL TEXT ]` button merges outputs into aggregate files (`all_newspaper.txt`, `all_newspaper1.txt`, etc.).
- **Dual Architecture**:
  - **Desktop App**: Native Windows Tkinter GUI (`main.py`) with 2-worker multiprocessing pool and page-level resume.
  - **Web App**: Flask API + Browser Dashboard (`api/index.py` & `public/`) deployed as a Docker Web Service on Render.

---

## Deploying to Render via Docker

### Recommended Production Deployment (1-Click Blueprint)

1. **Push Code to GitHub**:
   ```bash
   git add .
   git commit -m "Configure Render Docker container deployment with Tesseract OCR"
   git push origin main
   ```
2. **Deploy on Render**:
   - Log in to [render.com](https://render.com).
   - Click **New +** -> **Blueprint**.
   - Connect your GitHub repository `mihirbhatt13/newspaper-ocr-processor`.
   - Render automatically detects `render.yaml` and `Dockerfile`, installing `tesseract-ocr` and all language packs (`eng`, `hin`, `guj`, `mar`, `ben`, `tel`, `urd`).
   - Click **Apply**.

### Production Start Command
```bash
gunicorn -w 2 -b 0.0.0.0:$PORT api.index:app
```

---

## Local Development & Testing Options

### Option 1: Native Windows Desktop GUI
```bash
python main.py
```

### Option 2: Local Python Web Server
```bash
python api/index.py
```
Open browser at `http://localhost:5000`.

### Option 3: Local Docker Container Execution
Build and run the production Linux container locally using Docker:
```bash
docker build -t newspaper-ocr-processor .
docker run -p 5000:5000 newspaper-ocr-processor
```
Open browser at `http://localhost:5000`.

---

## License
MIT License
