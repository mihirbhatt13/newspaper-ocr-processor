# Newspaper OCR Processor

A reliable, high-performance Windows desktop GUI application to process batch newspaper PDFs and extract multilingual text using Tesseract OCR, PyPDFium2 in-memory page rendering, and state-based page-level resume deduplication.

---

## Features

- **Multilingual Support**:
  - Auto-detects installed Tesseract language packs (`hin`, `eng`, `guj`, `mar`, `ben`, `tel`, `urd`, `osd`, etc.).
  - Explicitly flags uninstalled language packs as `[Unavailable]` in dropdown options.
  - Supports single language and multi-language combinations (e.g. `Hindi + English`, `Gujarati + English`).
- **High-Performance Memory Pipeline**:
  - Uses `pypdfium2` for ultra-fast in-memory PDF page rendering (30ms per page).
  - Renders pages page-by-page in RAM without writing temporary PNG image files to disk.
  - Conservative default of **2 parallel worker processes** and **200 DPI resolution**.
- **Page-Level Resume & Deduplication**:
  - Remembers completed pages in `config/state.json`.
  - If a batch is interrupted, re-running skips completed pages and appends only missing ones with zero duplicate text.
- **Error Resilience**:
  - Process failure in one PDF does not stop remaining files in the batch.
  - Detailed errors are logged to `logs/ocr_YYYY-MM-DD.log`.
- **Text Combiner**:
  - Merges all individual `.txt` output files in `extracted_text/` into `combined/all_newspaper.txt` with formatted newspaper headers.

---

## Folder Structure

```
Newspaper_OCR_Processor/
│
├── app/
│   ├── main.py                  # Entry point
│   ├── config.py                # App configuration & path auto-discovery
│   ├── gui/
│   │   ├── main_window.py       # Main Tkinter UI Window
│   │   ├── settings_dialog.py   # Settings modal
│   │   └── widgets.py           # Custom review table & progress card
│   ├── ocr/
│   │   ├── ocr_engine.py        # Tesseract engine wrapper
│   │   └── worker.py            # Multiprocessing runner & page streamer
│   ├── pdf/
│   │   └── pdf_utils.py         # Page counter & in-memory page renderer
│   ├── combine/
│   │   └── text_combiner.py     # UTF-8 text merger with headers
│   └── utils/
│       ├── logger.py            # Rolling log manager
│       └── state_manager.py     # Thread-safe JSON state tracker
│
├── pdfs/                        # Input directory for newspaper PDFs
├── extracted_text/              # Processed text files per PDF
├── redo/                        # Folder for manual bad PDF re-runs
├── failed/                      # Error reports / logged bad PDFs
├── combined/                    # Output folder for all_newspaper.txt
├── logs/                        # Application logs
├── config/                      # app_config.json & state.json
├── tests/                       # Benchmark and test scripts
├── main.py                      # Application launcher
├── requirements.txt             # Python requirements
└── README.md                    # User manual
```

---

## How to Run

1. Open terminal inside the project folder:
   ```bash
   cd Newspaper_OCR_Processor
   ```

2. Run the application:
   ```bash
   python main.py
   ```

3. **Workflow**:
   - Click **Select PDF Folder** or **Select PDF Files**.
   - Select your OCR Language (e.g. `Auto` or `Hindi + English`).
   - Click **START OCR**.
   - Review extracted text in `extracted_text/`.
   - Click **Combine All Text** to produce `combined/all_newspaper.txt`.
