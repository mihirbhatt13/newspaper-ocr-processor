import os
import sys
import io
import datetime
import hashlib
from pathlib import Path
import streamlit as st

# Add project root to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, find_tesseract, get_installed_tesseract_languages, DEFAULT_LANG_MAP
from app.web_processor import (
    calculate_sha256_bytes,
    check_duplicates_batch,
    inspect_pdf_bytes,
    process_pdf_page_bytes,
    combine_texts_batch
)

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Newspaper OCR Processor - Free Cloud App",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for High-Contrast Progress Bars and Badges
st.markdown("""
<style>
    .main-header {
        font-size: 28px;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 4px;
    }
    .sub-header {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 20px;
    }
    .status-box-online {
        background-color: rgba(46, 125, 50, 0.15);
        color: #4ade80;
        border: 1px solid #2e7d32;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 600;
        margin-bottom: 20px;
    }
    .status-box-warning {
        background-color: rgba(230, 81, 0, 0.15);
        color: #fb923c;
        border: 1px solid #e65100;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 600;
        margin-bottom: 20px;
    }
    .stProgress > div > div > div > div {
        background-color: #1976D2;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "files_metadata" not in st.session_state:
    st.session_state.files_metadata = []
if "eligible_files" not in st.session_state:
    st.session_state.eligible_files = []
if "duplicate_files" not in st.session_state:
    st.session_state.duplicate_files = []
if "processed_results" not in st.session_state:
    st.session_state.processed_results = []
if "combined_output" not in st.session_state:
    st.session_state.combined_output = ""

# App Header
st.markdown('<div class="main-header">📰 Newspaper OCR Processor</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Free Streamlit Community Cloud Multilingual Newspaper Batch OCR & Deduplication System</div>', unsafe_allow_html=True)

# Detect Tesseract Engine Status
tess_cmd = find_tesseract()
installed_langs = get_installed_tesseract_languages(tess_cmd) if tess_cmd else []
tess_available = bool(tess_cmd and os.path.exists(tess_cmd))

if tess_available:
    st.markdown(
        f'<div class="status-box-online">🟢 Tesseract Engine Active (Path: <code>{tess_cmd}</code> | Languages: {", ".join(installed_langs)})</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        '<div class="status-box-warning">⚠️ Tesseract Engine Unavailable. Scanned PDF page OCR will report explicit engine error.</div>',
        unsafe_allow_html=True
    )

# Sidebar Configuration Controls
with st.sidebar:
    st.header("⚙️ OCR & Filter Controls")
    
    target_date = st.date_input(
        "Target Date Filter (Optional)",
        value=datetime.date(2026, 8, 9),
        help="Non-matching dates will be marked OUT-OF-DATE and excluded from OCR processing."
    )
    target_date_str = target_date.strftime("%Y-%m-%d")

    ocr_lang_display = st.selectbox(
        "OCR Language",
        options=["Auto", "English", "Hindi", "Gujarati", "Marathi", "Bengali", "Telugu", "Urdu"],
        index=0,
        help="Select language model for Tesseract OCR execution."
    )
    
    dpi_setting = st.slider(
        "Page Rendering Resolution (DPI)",
        min_value=100,
        max_value=300,
        value=150,
        step=50,
        help="Higher DPI improves OCR accuracy for fine print."
    )

# File Uploader Section
st.subheader("1. Select or Drop Newspaper PDF Files")
uploaded_files = st.file_uploader(
    "Choose PDF files from your device",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload single or multiple newspaper PDF files."
)

if uploaded_files:
    # Inspect newly uploaded files
    if len(st.session_state.files_metadata) != len(uploaded_files):
        st.session_state.files_metadata = []
        st.session_state.processed_results = []
        st.session_state.combined_output = ""

        with st.spinner(f"Inspecting {len(uploaded_files)} PDF file(s)..."):
            for f in uploaded_files:
                pdf_bytes = f.read()
                f.seek(0) # reset stream
                
                info = inspect_pdf_bytes(pdf_bytes, f.name)
                info["file_size"] = len(pdf_bytes)
                info["sha256"] = calculate_sha256_bytes(pdf_bytes)
                info["file_bytes"] = pdf_bytes
                info["status"] = "PENDING"
                info["ocr_status"] = "PENDING"
                info["extracted_text"] = ""
                st.session_state.files_metadata.append(info)

        st.session_state.eligible_files = list(st.session_state.files_metadata)
        st.session_state.duplicate_files = []

    st.success(f"Loaded {len(st.session_state.files_metadata)} PDF file(s) ready for inspection.")

    # Action Buttons Grid
    col1, col2, col3 = st.columns(3)

    with col1:
        btn_dup = st.button("🔍 Check Duplicates", use_container_width=True)

    with col2:
        btn_ocr = st.button("▶ Start OCR Processing", type="primary", use_container_width=True)

    with col3:
        btn_combine = st.button("📝 COMBINE ALL TEXT", use_container_width=True, disabled=len(st.session_state.processed_results) == 0)

    # 1. Handle Duplicate Check Action
    if btn_dup:
        meta_payload = [
            {
                "filename": m["filename"],
                "file_size": m["file_size"],
                "sha256": m["sha256"]
            }
            for m in st.session_state.files_metadata
        ]

        res = check_duplicates_batch(meta_payload, target_date_sel=target_date_str)
        eligible_names = {e["filename"] for e in res["eligible"]}

        st.session_state.eligible_files = [m for m in st.session_state.files_metadata if m["filename"] in eligible_names]
        st.session_state.duplicate_files = res["duplicates"]

        st.info(f"Duplicate Check Complete: {len(st.session_state.eligible_files)} Eligible PDF(s), {len(st.session_state.duplicate_files)} Duplicate/Out-of-date File(s).")

    # 2. Handle OCR Processing Action
    if btn_ocr:
        if not st.session_state.eligible_files:
            st.warning("No eligible PDF files available for OCR processing.")
        else:
            st.subheader("Live Processing Progress")
            
            pbar_batch = st.progress(0, text="Batch File Progress")
            pbar_pdf = st.progress(0, text="PDF Page Progress")
            lbl_status = st.empty()

            st.session_state.processed_results = []
            total_batch = len(st.session_state.eligible_files)

            for f_idx, file_info in enumerate(st.session_state.eligible_files):
                filename = file_info["filename"]
                pdf_bytes = file_info["file_bytes"]
                page_count = file_info["page_count"]

                lbl_status.markdown(f"**Processing File {f_idx + 1}/{total_batch}:** `{filename}` ({page_count} pages)...")
                pbar_batch.progress(int((f_idx / total_batch) * 100), text=f"Batch Progress: {f_idx + 1} / {total_batch} PDFs")

                full_file_text = ""
                has_error = False
                err_msg = ""
                file_diag = []

                for p_num in range(1, page_count + 1):
                    pbar_pdf.progress(int((p_num / page_count) * 100), text=f"File {f_idx + 1}: `{filename}` - Page {p_num} / {page_count}")
                    
                    res_p = process_pdf_page_bytes(
                        pdf_bytes=pdf_bytes,
                        filename=filename,
                        page_num=p_num,
                        lang_setting=ocr_lang_display,
                        dpi=dpi_setting
                    )

                    if res_p["success"]:
                        full_file_text += f"\n--- PAGE {p_num} ---\n" + res_p["text"]
                        file_diag.append({
                            "Page": p_num,
                            "Engine": res_p.get("engine_used", "N/A"),
                            "Image Size": res_p.get("img_dims", "N/A"),
                            "Selected Lang": res_p.get("language", "Auto"),
                            "Tesseract Path": res_p.get("tess_path", "N/A"),
                            "Tesseract Ver": res_p.get("tess_version", "N/A"),
                            "Chars Extracted": res_p.get("text_length", 0),
                            "Preview Snippet": res_p.get("preview_snippet", "")[:100]
                        })
                    else:
                        has_error = True
                        err_msg = res_p.get("message", "OCR Error")
                        if res_p.get("ocr_error") == "TESSERACT_UNAVAILABLE":
                            file_info["ocr_status"] = "ENGINE REQUIRED"
                        else:
                            file_info["ocr_status"] = "FAILED"
                        break

                if not has_error:
                    file_info["ocr_status"] = "COMPLETED"
                    file_info["extracted_text"] = full_file_text.strip()
                    st.session_state.processed_results.append({
                        "filename": filename,
                        "text": file_info["extracted_text"],
                        "diagnostics": file_diag
                    })
                else:
                    file_info["extracted_text"] = f"[ERROR]: {err_msg}"

            pbar_batch.progress(100, text="Batch File Progress Complete")
            pbar_pdf.progress(100, text="PDF Page Progress Complete")
            lbl_status.success(f"Processing Complete! Processed {len(st.session_state.processed_results)} PDF(s).")
            st.rerun()

    # 3. Handle Combine Action
    if btn_combine:
        if st.session_state.processed_results:
            st.session_state.combined_output = combine_texts_batch(st.session_state.processed_results)
            st.success("Combined all text outputs successfully!")

    # Render Eligible PDFs Review Queue Table
    st.subheader("2. PDF Review Queue")
    if st.session_state.eligible_files:
        queue_data = []
        for idx, m in enumerate(st.session_state.eligible_files, 1):
            queue_data.append({
                "#": idx,
                "PDF Filename": m["filename"],
                "Date": m["iso_date"] or "DATE UNKNOWN",
                "Pages": m["page_count"],
                "Type": "Scanned Image" if m["is_scanned"] else "Digital Text",
                "Dup Status": "UNIQUE",
                "OCR Status": m["ocr_status"],
                "Extracted Chars": len(m["extracted_text"]) if m["extracted_text"] else 0
            })
        st.dataframe(queue_data, use_container_width=True)
    else:
        st.info("No eligible PDF files in queue.")

    # Render Duplicates Table
    if st.session_state.duplicate_files:
        st.subheader("3. Duplicates & Excluded Files")
        dup_data = []
        for d in st.session_state.duplicate_files:
            dup_data.append({
                "PDF Filename": d["filename"],
                "Newspaper": d.get("newspaper_title", "-"),
                "Date": d.get("iso_date", "DATE UNKNOWN"),
                "Status / Reason": d.get("duplicate_of", "DUPLICATE"),
                "SHA-256 Hash": (d.get("sha256") or "")[:16] + "..."
            })
        st.dataframe(dup_data, use_container_width=True)

    # Render Processed Text Results & Individual Downloads
    if st.session_state.processed_results:
        st.subheader("4. Extracted Text Results & Export")
        
        for item in st.session_state.processed_results:
            with st.expander(f"📄 {item['filename']} (Extracted Text Preview - {len(item['text'])} Chars)", expanded=True):
                st.text_area("Extracted Text", value=item["text"], height=250, key=f"txt_{item['filename']}")
                
                if item.get("diagnostics"):
                    with st.expander("🔍 OCR Pipeline Diagnostic Details"):
                        st.dataframe(item["diagnostics"], use_container_width=True)

                st.download_button(
                    label=f"💾 Download {item['filename']}.txt",
                    data=item["text"],
                    file_name=f"{item['filename']}.txt",
                    mime="text/plain",
                    key=f"dl_{item['filename']}"
                )


    # Render Aggregate Combined Text Output
    if st.session_state.combined_output:
        st.subheader("5. Combined Aggregate Text Output")
        st.text_area("Combined Text Output (all_newspaper.txt)", value=st.session_state.combined_output, height=350)
        st.download_button(
            label="💾 Download Combined Text File (all_newspaper.txt)",
            data=st.session_state.combined_output,
            file_name="all_newspaper.txt",
            mime="text/plain"
        )
