import os
import sys
import time
import queue
import shutil
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from app.config import ConfigManager, DIRS, DEFAULT_LANG_MAP, get_installed_tesseract_languages
from app.pdf.pdf_utils import get_pdf_page_count
from app.ocr.worker import process_pdf_file, _worker_process_single_pdf
from app.utils.state_manager import StateManager
from app.utils.file_utils import calculate_sha256
from app.utils.date_parser import extract_newspaper_date, extract_newspaper_info
from app.utils.logger import get_logger

from app.combine.text_combiner import combine_all_text_files
from app.gui.widgets import ReviewTable, ProgressCard, DuplicateTable
from app.gui.settings_dialog import SettingsDialog

class MainWindow(tk.Tk):
    """Main Application Window for Newspaper OCR Processor GUI."""
    def __init__(self):
        super().__init__()
        self.title("Newspaper OCR Processor - Multilingual Desktop Batch OCR")
        self.geometry("960x760")
        self.minsize(880, 680)

        self.cfg_mgr = ConfigManager()
        self.state_mgr = StateManager()
        self.logger = get_logger()

        self.selected_pdfs = []
        self.ocr_queue = []
        self.duplicate_records = []
        self.has_checked_duplicates = False
        self.total_pages_count = 0
        self.is_processing = False
        self.stop_requested = False
        self.msg_queue = queue.Queue()

        self._apply_styles()
        self._build_ui()
        self.after(100, self._process_queue_messages)

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        
        style.configure("TFrame", background="#f8f9fa")
        style.configure("TLabel", background="#f8f9fa", font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1a237e", background="#e8eaf6")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground="#37474f", background="#e8eaf6")
        style.configure("TLabelframe", background="#f8f9fa")
        style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"), foreground="#1a237e")

        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), background="#1b5e20", foreground="white")
        style.map("Accent.TButton", background=[("active", "#2e7d32"), ("disabled", "#c8e6c9")])

        style.configure("DupCheck.TButton", font=("Segoe UI", 10, "bold"), background="#4a148c", foreground="white")
        style.map("DupCheck.TButton", background=[("active", "#6a1b9a"), ("disabled", "#e1bee7")])

        style.configure("Stop.TButton", font=("Segoe UI", 10, "bold"), background="#c62828", foreground="white")
        style.map("Stop.TButton", background=[("active", "#b71c1c"), ("disabled", "#ffcdd2")])

        # High-Contrast Progress Bar Styles
        # PDF Progress: Vibrant Blue fill on light neutral grey background
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor="#E0E0E0",     # Light neutral grey background
                        background="#1976D2",      # High-contrast vibrant blue fill
                        bordercolor="#BDBDBD",     # Subtle neutral border
                        lightcolor="#1976D2",
                        darkcolor="#1976D2",
                        thickness=18)

        # Batch Progress: Vibrant Green fill on light neutral grey background
        style.configure("Green.Horizontal.TProgressbar",
                        troughcolor="#E0E0E0",     # Light neutral grey background
                        background="#2E7D32",      # High-contrast vibrant green fill
                        bordercolor="#BDBDBD",     # Subtle neutral border
                        lightcolor="#2E7D32",
                        darkcolor="#2E7D32",
                        thickness=18)


    def _build_ui(self):
        # Top Header Banner
        header_frame = ttk.Frame(self, style="TFrame", padding=(16, 12))
        header_frame.configure(style="TFrame")
        header_container = tk.Frame(header_frame, bg="#e8eaf6", bd=1, relief="solid")
        header_container.pack(fill="x")

        lbl_header = ttk.Label(header_container, text="  NEWSPAPER OCR PROCESSOR", style="Header.TLabel")
        lbl_header.pack(anchor="w", padx=12, pady=(10, 2))
        lbl_sub = ttk.Label(header_container, text="  Multilingual Batch PDF OCR & Text Aggregator (Offline Tesseract Engine)", style="Subtitle.TLabel")
        lbl_sub.pack(anchor="w", padx=12, pady=(0, 10))

        header_frame.pack(fill="x")

        # Main Body Frame
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        # --- Top Controls Frame: File Selection & Language ---
        ctrl_frame = ttk.LabelFrame(body, text="Input Selection & OCR Language", padding=12)
        ctrl_frame.pack(fill="x", pady=(0, 12))

        # Row 1: Folder / File Buttons + Count Labels
        f_select = ttk.Frame(ctrl_frame)
        f_select.pack(fill="x", pady=(0, 8))

        btn_folder = ttk.Button(f_select, text="📁 Select PDF Folder", command=self._select_pdf_folder)
        btn_folder.pack(side="left", padx=(0, 8))

        btn_files = ttk.Button(f_select, text="📄 Select PDF Files", command=self._select_pdf_files)
        btn_files.pack(side="left", padx=(0, 12))

        ttk.Label(f_select, text="Target Date:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.cmb_target_date = ttk.Combobox(f_select, state="readonly", width=18)
        self.cmb_target_date["values"] = ["All Dates (Default)"]
        self.cmb_target_date.set("All Dates (Default)")
        self.cmb_target_date.pack(side="left", padx=(0, 4))

        btn_cal = ttk.Button(f_select, text="📅 Calendar", command=self._open_calendar_picker)
        btn_cal.pack(side="left", padx=(0, 12))

        self.btn_dup_check = ttk.Button(f_select, text="🔍 Check Duplicates", style="DupCheck.TButton", command=self._check_duplicates)
        self.btn_dup_check.pack(side="left", padx=(0, 16))



        self.lbl_counts = ttk.Label(f_select, text="Total PDFs: 0  |  Unique PDFs: 0  |  Duplicates: 0  |  OCR Queue: 0", font=("Segoe UI", 9, "bold"), foreground="#0d47a1")
        self.lbl_counts.pack(side="left", padx=4)

        # Row 2: OCR Language Selector + Action Buttons
        f_lang = ttk.Frame(ctrl_frame)
        f_lang.pack(fill="x")

        ttk.Label(f_lang, text="OCR Language:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))

        self.cmb_lang = ttk.Combobox(f_lang, state="readonly", width=32)
        self.cmb_lang.pack(side="left", padx=(0, 16))
        self._refresh_language_dropdown()

        # Action Buttons: START / STOP / COMBINE ALL TEXT
        self.btn_start = ttk.Button(f_lang, text="▶ START OCR", style="Accent.TButton", command=self._start_ocr_process)
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = ttk.Button(f_lang, text="⏹ STOP", style="Stop.TButton", command=self._stop_ocr_process, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 16))

        self.btn_combine = ttk.Button(f_lang, text="📝 COMBINE ALL TEXT", command=self._combine_all_text, state="disabled")
        self.btn_combine.pack(side="left", padx=(0, 8))


        # --- Progress Card ---
        self.progress_card = ProgressCard(body)
        self.progress_card.pack(fill="x", pady=(0, 12))

        # --- Status Summary Bar ---
        f_summary = ttk.Frame(body)
        f_summary.pack(fill="x", pady=(0, 8))

        self.lbl_sum_success = ttk.Label(f_summary, text="SUCCESS: 0", font=("Segoe UI", 9, "bold"), foreground="#1b5e20")
        self.lbl_sum_success.pack(side="left", padx=(0, 16))

        self.lbl_sum_failed = ttk.Label(f_summary, text="FAILED: 0", font=("Segoe UI", 9, "bold"), foreground="#b71c1c")
        self.lbl_sum_failed.pack(side="left", padx=(0, 16))

        self.lbl_sum_review = ttk.Label(f_summary, text="NEEDS REVIEW: 0", font=("Segoe UI", 9, "bold"), foreground="#e65100")
        self.lbl_sum_review.pack(side="left", padx=(0, 16))

        self.lbl_sum_duplicate = ttk.Label(f_summary, text="DUPLICATES: 0", font=("Segoe UI", 9, "bold"), foreground="#4a148c")
        self.lbl_sum_duplicate.pack(side="left", padx=(0, 16))

        self.lbl_sum_pending = ttk.Label(f_summary, text="PENDING: 0", font=("Segoe UI", 9, "bold"), foreground="#616161")
        self.lbl_sum_pending.pack(side="left")

        # --- Notebook Container for Tables ---
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True, pady=(0, 12))

        # Tab 1: All PDFs (Review Table)
        self.tab_all_pdfs = ttk.Frame(self.notebook)
        self.review_table = ReviewTable(self.tab_all_pdfs, on_select_callback=self._on_table_row_selected)
        self.review_table.pack(fill="both", expand=True)

        f_redo_actions = ttk.Frame(self.tab_all_pdfs, padding=(0, 8, 0, 0))
        f_redo_actions.pack(fill="x")

        btn_move_redo = ttk.Button(f_redo_actions, text="🔄 Move Selected to Redo", command=self._move_selected_to_redo)
        btn_move_redo.pack(side="left", padx=(0, 8))

        self.notebook.add(self.tab_all_pdfs, text=" All PDFs (Review Table) ")


        # Tab 2: Duplicate PDFs (Results Table)
        self.tab_duplicates = ttk.Frame(self.notebook)
        self.duplicate_table = DuplicateTable(self.tab_duplicates)
        self.duplicate_table.pack(fill="both", expand=True)

        # Actions toolbar on Duplicate Tab
        f_dup_actions = ttk.Frame(self.tab_duplicates, padding=(0, 8, 0, 0))
        f_dup_actions.pack(fill="x")

        btn_rm_dup_queue = ttk.Button(f_dup_actions, text="🗑 Remove Duplicates from Queue", command=self._remove_duplicates_from_queue)
        btn_rm_dup_queue.pack(side="left", padx=(0, 8))

        btn_move_dup = ttk.Button(f_dup_actions, text="📦 Move Duplicates", command=self._move_duplicates_folder)
        btn_move_dup.pack(side="left", padx=(0, 8))

        btn_open_dup = ttk.Button(f_dup_actions, text="📁 Open Duplicates Folder", command=self._open_duplicates_folder)
        btn_open_dup.pack(side="left")

        self.notebook.add(self.tab_duplicates, text=" Duplicate PDFs (Results) ")

        # --- Bottom Operational Buttons Bar ---
        f_bottom = ttk.Frame(body)
        f_bottom.pack(fill="x", side="bottom")

        btn_open_text = ttk.Button(f_bottom, text="📄 OPEN EXTRACTED TEXT", command=self._open_extracted_text_folder)
        btn_open_text.pack(side="left", padx=(0, 6))

        btn_open_redo = ttk.Button(f_bottom, text="🔄 OPEN REDO", command=self._open_redo_folder)
        btn_open_redo.pack(side="left", padx=(0, 6))

        btn_open_dup_bot = ttk.Button(f_bottom, text="🔍 OPEN DUPLICATES", command=self._open_duplicates_folder)
        btn_open_dup_bot.pack(side="left", padx=(0, 6))

        btn_open_comb = ttk.Button(f_bottom, text="📦 OPEN COMBINED", command=self._open_combined_folder)
        btn_open_comb.pack(side="left", padx=(0, 6))

        btn_logs = ttk.Button(f_bottom, text="📋 OPEN LOGS", command=self._open_logs_folder)
        btn_logs.pack(side="left", padx=(0, 6))


        btn_settings = ttk.Button(f_bottom, text="⚙ Settings", command=self._open_settings)
        btn_settings.pack(side="right")


    def _refresh_language_dropdown(self):
        tess_cmd = self.cfg_mgr.get("tesseract_cmd")
        installed = set(get_installed_tesseract_languages(tess_cmd))

        options = ["Auto"]
        for ui_name, code in DEFAULT_LANG_MAP.items():
            if ui_name == "Auto":
                continue
            if code in installed:
                options.append(ui_name)
            else:
                options.append(f"{ui_name} [Unavailable]")

        combos = [
            ("Hindi + English", ["hin", "eng"]),
            ("Gujarati + English", ["guj", "eng"]),
            ("Marathi + English", ["mar", "eng"]),
            ("Tamil + English", ["tam", "eng"]),
            ("Telugu + English", ["tel", "eng"]),
            ("Bengali + English", ["ben", "eng"]),
        ]

        for combo_name, codes in combos:
            if all(c in installed for c in codes):
                options.append(combo_name)
            else:
                options.append(f"{combo_name} [Unavailable]")

        self.cmb_lang["values"] = options
        default_sel = self.cfg_mgr.get("ocr_language", "Auto")
        if default_sel in options:
            self.cmb_lang.set(default_sel)
        else:
            self.cmb_lang.set("Auto")

    def _open_calendar_picker(self):
        """Opens an interactive native Tkinter month calendar popup window."""
        import calendar
        from datetime import datetime

        popup = tk.Toplevel(self)
        popup.title("Select Target Publication Date")
        popup.geometry("320x300")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()

        now = datetime.now()
        year_var = tk.IntVar(value=now.year)
        month_var = tk.IntVar(value=now.month)

        f_hdr = ttk.Frame(popup, padding=8)
        f_hdr.pack(fill="x")

        f_grid = ttk.Frame(popup, padding=8)
        f_grid.pack(fill="both", expand=True)

        def update_calendar():
            for widget in f_grid.winfo_children():
                widget.destroy()

            y = year_var.get()
            m = month_var.get()
            lbl_month_year.config(text=f"{calendar.month_name[m]} {y}")

            headers = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
            for col, h in enumerate(headers):
                lbl = ttk.Label(f_grid, text=h, font=("Segoe UI", 9, "bold"), anchor="center")
                lbl.grid(row=0, column=col, sticky="ew", padx=2, pady=2)

            month_cal = calendar.monthcalendar(y, m)
            for row_idx, week in enumerate(month_cal, start=1):
                for col_idx, day in enumerate(week):
                    if day != 0:
                        d_str = f"{day:02d}-{m:02d}-{y}"
                        iso_str = f"{y:04d}-{m:02d}-{day:02d}"

                        def make_cmd(selected_date=d_str, selected_iso=iso_str):
                            def select_date():
                                vals = list(self.cmb_target_date["values"])
                                if selected_iso not in vals:
                                    vals.append(selected_iso)
                                if selected_date not in vals:
                                    vals.append(selected_date)
                                self.cmb_target_date["values"] = vals
                                self.cmb_target_date.set(selected_iso)
                                popup.destroy()
                            return select_date

                        btn_day = ttk.Button(f_grid, text=str(day), width=3, command=make_cmd())
                        btn_day.grid(row=row_idx, column=col_idx, padx=2, pady=2)

        def prev_month():
            m = month_var.get() - 1
            if m < 1:
                month_var.set(12)
                year_var.set(year_var.get() - 1)
            else:
                month_var.set(m)
            update_calendar()

        def next_month():
            m = month_var.get() + 1
            if m > 12:
                month_var.set(1)
                year_var.set(year_var.get() + 1)
            else:
                month_var.set(m)
            update_calendar()

        btn_prev = ttk.Button(f_hdr, text="◀", width=3, command=prev_month)
        btn_prev.pack(side="left")

        lbl_month_year = ttk.Label(f_hdr, text="", font=("Segoe UI", 10, "bold"))
        lbl_month_year.pack(side="left", expand=True)

        btn_next = ttk.Button(f_hdr, text="▶", width=3, command=next_month)
        btn_next.pack(side="right")

        update_calendar()


    def _select_pdf_folder(self):
        folder = filedialog.askdirectory(title="Select Folder Containing Newspaper PDFs")
        if folder:
            all_pdfs = set(Path(folder).glob("*.pdf")) | set(Path(folder).glob("*.PDF"))
            pdf_paths = sorted(list(all_pdfs))
            if not pdf_paths:
                messagebox.showinfo("No PDFs Found", f"No PDF files were found inside directory:\n{folder}")
                return
            self._load_selected_pdfs(pdf_paths)

    def _select_pdf_files(self):
        files = filedialog.askopenfilenames(
            title="Select Newspaper PDF Files",
            filetypes=[("PDF Files", "*.pdf;*.PDF"), ("All Files", "*.*")]
        )
        if files:
            unique_files = list(dict.fromkeys(files))
            pdf_paths = [Path(f) for f in unique_files]
            self._load_selected_pdfs(pdf_paths)

    def _load_selected_pdfs(self, pdf_paths):
        seen = set()
        unique_paths = []
        for p in pdf_paths:
            resolved = str(p.resolve())
            if resolved not in seen:
                seen.add(resolved)
                unique_paths.append(p)

        self.selected_pdfs = unique_paths
        self.current_batch_pdfs = list(self.selected_pdfs)
        self.ocr_queue = list(self.selected_pdfs)
        self.duplicate_records = []
        self.has_checked_duplicates = False
        if hasattr(self, "btn_combine"):
            self.btn_combine.config(state="disabled")


        popp_path = self.cfg_mgr.get("poppler_path")
        self.review_table.clear()
        self.duplicate_table.clear()
        
        self.total_pages_count = 0
        for pdf in self.selected_pdfs:
            try:
                pages = get_pdf_page_count(pdf, poppler_path=popp_path)
            except Exception:
                pages = 0
            self.total_pages_count += pages
            
            sha256 = None
            try:
                if pdf.exists():
                    sha256 = calculate_sha256(pdf)
            except Exception:
                pass

            info = self.state_mgr.get_file_state(pdf.name, sha256_hash=sha256)
            completed_pages = self.state_mgr.get_completed_pages(pdf.name, sha256_hash=sha256)
            status = info.get("status", "PENDING")
            if status not in ["NEEDS REVIEW", "FAILED", "DUPLICATE"]:
                status = "SUCCESS" if (len(completed_pages) == pages and pages > 0) else "PENDING"
            
            date_str = info.get("date_extracted", "")
            if not date_str or date_str == "DATE UNKNOWN":
                iso, _ = extract_newspaper_date(pdf.name)
                date_str = iso if iso else "DATE UNKNOWN"

            dur = info.get("duration_sec", 0.0)

            self.review_table.update_item(
                pdf.name,
                date_str,
                pages,
                len(completed_pages),
                status,
                self.cmb_lang.get(),
                dur
            )

        total_cnt = len(self.selected_pdfs)
        self.lbl_counts.config(
            text=f"Total PDFs: {total_cnt}  |  Unique PDFs: --  |  Duplicates: --  |  OCR Queue: {total_cnt}"
        )
        self.btn_start.config(text="▶ START OCR")

        # Scan extracted dates and populate target date combobox
        dates_found = set()
        for pdf in self.selected_pdfs:
            newspaper_title, iso_date = extract_newspaper_info(pdf.name)
            if iso_date and iso_date != "DATE UNKNOWN":
                dates_found.add(iso_date)

        target_date_options = ["All Dates (Default)"] + sorted(list(dates_found))
        self.cmb_target_date["values"] = target_date_options
        self.cmb_target_date.set("All Dates (Default)")

        self._update_summary_counts()

    def _check_duplicates(self):
        if not self.selected_pdfs:
            messagebox.showwarning("No PDFs Selected", "Please select a PDF folder or PDF files before checking duplicates.")
            return

        target_date_sel = self.cmb_target_date.get()
        has_date_filter = (target_date_sel and target_date_sel != "All Dates (Default)")

        target_iso, _ = extract_newspaper_date(target_date_sel)
        if not target_iso:
            target_iso = target_date_sel.strip()

        self.progress_card.lbl_status.config(text="Status: Checking SHA-256 hashes and metadata for duplicates...")
        self.update_idletasks()

        # Map: (filename, file_size_bytes, file_extension, sha256_hash) -> (original_pdf_path, original_filename)
        seen_files_map = {}
        self.ocr_queue = []
        self.duplicate_records = []
        self.duplicate_table.clear()

        popp_path = self.cfg_mgr.get("poppler_path")
        total_sel = len(self.selected_pdfs)

        for idx, pdf in enumerate(self.selected_pdfs, 1):
            if idx % 5 == 0 or idx == total_sel:
                self.progress_card.lbl_status.config(text=f"Status: Checking duplicates: {idx} / {total_sel}...")
                self.update_idletasks()

            try:
                sha256 = calculate_sha256(pdf)
                file_size = pdf.stat().st_size if pdf.exists() else 0
            except Exception as e:
                self.logger.error(f"Failed to inspect PDF {pdf.name}: {e}")
                continue

            file_ext = pdf.suffix.lower()
            newspaper_title, iso_date = extract_newspaper_info(pdf.name)
            is_known_date = bool(iso_date and iso_date != "DATE UNKNOWN")

            # Target date filtering: if target date is set AND PDF date is KNOWN AND does not match, mark DUPLICATE / OUT-OF-DATE
            # UNKNOWN dates are NEVER rejected by the target date filter.
            if has_date_filter and is_known_date and iso_date != target_iso:
                dup_label = f"OUT-OF-DATE (Target: {target_date_sel})"
                rec = {
                    "pdf_filename": pdf.name,
                    "pdf_path": pdf,
                    "newspaper": newspaper_title,
                    "date": iso_date,
                    "duplicate_of": dup_label,
                    "sha256": sha256,
                    "status": "DUPLICATE"
                }
                self.duplicate_records.append(rec)
                self.duplicate_table.update_item(pdf.name, newspaper_title, iso_date, dup_label, sha256, "DUPLICATE")
                
                try:
                    pages = get_pdf_page_count(pdf, poppler_path=popp_path)
                except Exception:
                    pages = 0
                self.review_table.update_item(pdf.name, iso_date, pages, 0, "OUT-OF-DATE", self.cmb_lang.get(), 0.0)
                continue


            # Exact Duplicate Check: ALL 4 must match (Filename, File Size, File Extension, SHA-256 Hash)
            exact_key = (pdf.name, file_size, file_ext, sha256)
            if exact_key in seen_files_map:
                orig_path, orig_name = seen_files_map[exact_key]
                rec = {
                    "pdf_filename": pdf.name,
                    "pdf_path": pdf,
                    "newspaper": newspaper_title,
                    "date": iso_date,
                    "duplicate_of": orig_name,
                    "sha256": sha256,
                    "status": "DUPLICATE"
                }
                self.duplicate_records.append(rec)
                self.duplicate_table.update_item(pdf.name, newspaper_title, iso_date, orig_name, sha256, "DUPLICATE")
                
                try:
                    pages = get_pdf_page_count(pdf, poppler_path=popp_path)
                except Exception:
                    pages = 0
                self.review_table.update_item(pdf.name, iso_date, pages, 0, "DUPLICATE", self.cmb_lang.get(), 0.0)
            else:
                seen_files_map[exact_key] = (pdf, pdf.name)
                self.ocr_queue.append(pdf)


        # Physically organize files into unique/ and duplicates/
        unique_dir = DIRS["unique"]
        unique_dir.mkdir(parents=True, exist_ok=True)
        dup_dir = DIRS["duplicates"]
        dup_dir.mkdir(parents=True, exist_ok=True)

        new_ocr_queue = []
        for pdf in self.ocr_queue:
            if pdf.parent != unique_dir and pdf.exists():
                try:
                    dest = unique_dir / pdf.name
                    if dest.exists():
                        short_h = calculate_sha256(pdf)[:8]
                        dest = unique_dir / f"{pdf.stem}_{short_h}.pdf"
                    shutil.move(str(pdf), str(dest))
                    new_ocr_queue.append(dest)
                except Exception as e:
                    self.logger.error(f"Failed to move unique PDF {pdf.name} to unique/: {e}")
                    new_ocr_queue.append(pdf)
            else:
                new_ocr_queue.append(pdf)

        self.ocr_queue = new_ocr_queue

        for rec in self.duplicate_records:
            pdf_path = rec.get("pdf_path")
            if pdf_path and pdf_path.parent != dup_dir and pdf_path.exists():
                try:
                    dest = dup_dir / pdf_path.name
                    if dest.exists():
                        short_h = rec.get("sha256", calculate_sha256(pdf_path))[:8]
                        dest = dup_dir / f"{pdf_path.stem}_{short_h}.pdf"
                    shutil.move(str(pdf_path), str(dest))
                    rec["pdf_path"] = dest
                except Exception as e:
                    self.logger.error(f"Failed to move duplicate PDF {pdf_path.name} to duplicates/: {e}")

        self.has_checked_duplicates = True
        self.current_batch_pdfs = list(self.ocr_queue)
        if hasattr(self, "btn_combine"):
            self.btn_combine.config(state="disabled")

        unique_count = len(self.ocr_queue)

        dup_count = len(self.duplicate_records)
        total_count = len(self.selected_pdfs)

        filter_msg = f" (Filtered to target date {target_date_sel})" if has_date_filter else ""
        self.lbl_counts.config(
            text=f"Total PDFs: {total_count}  |  Unique PDFs: {unique_count}  |  Duplicates: {dup_count}  |  OCR Queue: {unique_count}"
        )
        self.btn_start.config(text=f"▶ START OCR ({unique_count} PDFs)")
        self.progress_card.lbl_status.config(
            text=f"Status: Duplicate check completed. {unique_count} unique, {dup_count} duplicate(s){filter_msg}."
        )
        self._update_summary_counts()

        if dup_count > 0:
            self.notebook.select(self.tab_duplicates)
            messagebox.showinfo("Duplicate Check Complete", 
                                f"Duplicate check complete{filter_msg}!\n\nTotal PDFs: {total_count}\nUnique PDFs: {unique_count}\nDuplicates / Out-of-Date: {dup_count}\n\nUnique PDFs moved to unique/ folder.\nDuplicates moved to duplicates/ folder.")
        else:
            messagebox.showinfo("Duplicate Check Complete", f"Duplicate check complete{filter_msg}! All {total_count} PDFs are unique and moved to unique/ folder.")



    def _remove_duplicates_from_queue(self):
        if not self.duplicate_records:
            messagebox.showinfo("No Duplicates", "There are no duplicate PDFs in the current selection.")
            return

        dup_names = set(r["pdf_filename"] for r in self.duplicate_records)
        orig_queue_len = len(self.ocr_queue)
        self.ocr_queue = [p for p in self.ocr_queue if p.name not in dup_names]
        
        unique_count = len(self.ocr_queue)
        dup_count = len(self.duplicate_records)
        total_count = len(self.selected_pdfs)

        self.lbl_counts.config(
            text=f"Total PDFs: {total_count}  |  Unique PDFs: {unique_count}  |  Duplicates: {dup_count}  |  OCR Queue: {unique_count}"
        )
        self.btn_start.config(text=f"▶ START OCR ({unique_count} PDFs)")
        messagebox.showinfo("Queue Updated", f"Removed {dup_count} duplicate PDF(s) from the active OCR queue.\n\nOriginal PDF files on disk remain safe and untouched.")

    def _move_duplicates_folder(self):
        if not self.duplicate_records:
            messagebox.showinfo("No Duplicates", "There are no duplicate PDFs to move.")
            return

        dup_count = len(self.duplicate_records)
        ans = messagebox.askyesno(
            "Move Duplicate PDFs",
            f"Are you sure you want to move {dup_count} duplicate PDF file(s) to the duplicates/ folder?\n\nOriginal files will be relocated safely inside your project directory."
        )
        if not ans:
            return

        dup_dir = DIRS["duplicates"]
        dup_dir.mkdir(parents=True, exist_ok=True)

        moved_count = 0
        for rec in list(self.duplicate_records):
            pdf_path = rec.get("pdf_path")
            if pdf_path and pdf_path.exists():
                try:
                    dest = dup_dir / pdf_path.name
                    if dest.exists():
                        short_h = rec["sha256"][:8]
                        dest = dup_dir / f"{pdf_path.stem}_{short_h}.pdf"
                    shutil.move(str(pdf_path), str(dest))
                    moved_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to move duplicate {pdf_path.name}: {e}")

        messagebox.showinfo("Move Duplicates Complete", f"Successfully moved {moved_count} duplicate PDF(s) to:\n{dup_dir}")

    def _open_duplicates_folder(self):
        folder = str(DIRS["duplicates"])
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def _move_selected_to_redo(self):
        selected_item = self.review_table.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a PDF row from the table to move to the Redo folder.")
            return

        values = self.review_table.tree.item(selected_item[0])["values"]
        filename = values[0]
        status = values[4]

        if status == "SUCCESS":
            messagebox.showwarning("Cannot Move SUCCESS PDF", f"PDF '{filename}' completed successfully (SUCCESS) and cannot be moved to the Redo folder.")
            return

        if status == "DUPLICATE":
            messagebox.showwarning("Cannot Move DUPLICATE PDF", f"PDF '{filename}' is marked DUPLICATE and cannot be moved to the Redo folder.\n\nUse 'Move Duplicates' on the Duplicate tab instead.")
            return

        if status not in ["NEEDS REVIEW", "FAILED"]:
            messagebox.showinfo("Move to Redo", f"Only PDFs with status 'NEEDS REVIEW' or 'FAILED' are eligible for the Redo workflow. Current status is '{status}'.")
            return

        ans = messagebox.askyesno(
            "Move PDF to Redo Folder",
            f"Are you sure you want to move '{filename}' to the redo/ folder for manual Cloud AI processing?\n\nThe original PDF file will be relocated safely inside your project directory."
        )
        if not ans:
            return

        redo_dir = DIRS["redo"]
        redo_dir.mkdir(parents=True, exist_ok=True)

        target_path = None
        for p in self.selected_pdfs:
            if p.name == filename:
                target_path = p
                break

        if not target_path or not target_path.exists():
            messagebox.showerror("File Not Found", f"Could not find original PDF file on disk for '{filename}'.")
            return

        try:
            dest_path = redo_dir / filename
            if dest_path.exists():
                sha256 = calculate_sha256(target_path)
                short_h = sha256[:8]
                dest_path = redo_dir / f"{target_path.stem}_{short_h}.pdf"
            
            shutil.move(str(target_path), str(dest_path))
            
            sha256 = calculate_sha256(dest_path) if dest_path.exists() else None
            self.state_mgr.mark_needs_review(filename, f"Moved to redo folder: {dest_path}", sha256_hash=sha256)
            
            date_str = values[1]
            pages = values[2]
            dur = values[6]
            dur_sec = float(dur.replace("s", "")) if (dur and dur != "--") else 0.0
            
            self.review_table.update_item(
                filename,
                date_str,
                pages,
                values[3],
                "MOVED TO REDO",
                self.cmb_lang.get(),
                dur_sec
            )
            self._update_summary_counts()
            
            messagebox.showinfo("Moved to Redo", f"Successfully moved '{filename}' to:\n{dest_path}")
        except Exception as e:
            self.logger.error(f"Failed to move '{filename}' to redo: {e}")
            messagebox.showerror("Move Failed", f"Failed to move file to redo: {e}")


    def _update_summary_counts(self):
        succ = 0
        dup = 0
        rev = 0
        fail = 0
        pend = 0

        for item in self.review_table.tree.get_children():
            values = self.review_table.tree.item(item)["values"]
            status = values[4]
            if status == "SUCCESS":
                succ += 1
            elif status == "DUPLICATE":
                dup += 1
            elif status == "NEEDS REVIEW":
                rev += 1
            elif status == "FAILED":
                fail += 1
            else:
                pend += 1

        self.lbl_sum_success.config(text=f"SUCCESS: {succ}")
        self.lbl_sum_failed.config(text=f"FAILED: {fail}")
        self.lbl_sum_review.config(text=f"NEEDS REVIEW: {rev}")
        self.lbl_sum_duplicate.config(text=f"DUPLICATES: {dup}")
        self.lbl_sum_pending.config(text=f"PENDING: {pend}")


    def _start_ocr_process(self):
        if not self.selected_pdfs:
            messagebox.showwarning("No PDFs Selected", "Please select a PDF folder or PDF files before starting OCR.")
            return

        target_pdfs = self.ocr_queue if self.has_checked_duplicates else self.selected_pdfs
        if not target_pdfs:
            messagebox.showinfo("OCR Queue Empty", "There are no PDFs remaining in the OCR queue to process.")
            return

        lang_setting = self.cmb_lang.get()
        if "[Unavailable]" in lang_setting:
            clean_name = lang_setting.replace("[Unavailable]", "").strip()
            messagebox.showerror("Language Missing", 
                                 f"The selected language combination '{clean_name}' cannot be used because its Tesseract language traineddata is not installed on your system.")
            return

        self.is_processing = True
        self.stop_requested = False
        self.current_batch_pdfs = list(target_pdfs)
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.cmb_lang.config(state="disabled")
        self.btn_dup_check.config(state="disabled")
        if hasattr(self, "btn_combine"):
            self.btn_combine.config(state="disabled")

        self.cfg_mgr.set("ocr_language", lang_setting)


        # Initialize Progress Card for OCR batch start
        self.progress_card.update_progress(
            filename=target_pdfs[0].name,
            current_page=0,
            total_pages=0,
            pdf_index=1,
            total_pdfs=len(target_pdfs),
            status_msg="Starting OCR batch...",
            elapsed_sec=0,
            remaining_sec=None
        )

        t = threading.Thread(target=self._run_ocr_batch_thread, daemon=True)
        t.start()

    def _stop_ocr_process(self):
        if self.is_processing:
            self.stop_requested = True
            self.progress_card.lbl_status.config(text="Status: Stopping after current page...")
            self.btn_stop.config(state="disabled")

    def _run_ocr_batch_thread(self):
        """Background thread executing batch OCR via ProcessPoolExecutor or queue worker."""
        config_dict = dict(self.cfg_mgr.config)
        num_workers = config_dict.get("ocr_workers", 2)
        target_pdfs = self.ocr_queue if self.has_checked_duplicates else self.selected_pdfs
        total_pdfs = len(target_pdfs)

        start_batch_time = time.time()
        completed_pdfs_count = 0
        total_processed_pages = 0

        def progress_callback(pdf_name, page_num, total_pages, status_msg):
            nonlocal total_processed_pages
            elapsed = time.time() - start_batch_time
            avg_per_page = elapsed / max(1, total_processed_pages) if total_processed_pages > 0 else 0
            rem_pages = max(0, self.total_pages_count - total_processed_pages)
            rem_time = rem_pages * avg_per_page if avg_per_page > 0 else None

            self.msg_queue.put({
                "type": "PROGRESS",
                "pdf_filename": pdf_name,
                "current_page": page_num,
                "total_pages": total_pages,
                "pdf_index": completed_pdfs_count + 1,
                "total_pdfs": total_pdfs,
                "status_msg": status_msg,
                "elapsed": elapsed,
                "remaining": rem_time
            })

        try:
            if num_workers == 1:
                for i, pdf_path in enumerate(target_pdfs, 1):
                    if self.stop_requested:
                        break
                    try:
                        res = process_pdf_file(pdf_path, config_dict, progress_callback=progress_callback)
                        total_processed_pages += res.get("processed_pages", 0)
                        completed_pdfs_count += 1
                        self.msg_queue.put({"type": "PDF_FINISHED", "result": res})
                    except Exception as e:
                        self.logger.error(f"Error processing {pdf_path.name}: {e}")
                        self.state_mgr.mark_failed(pdf_path.name, str(e))
                        self.msg_queue.put({
                            "type": "PDF_FINISHED",
                            "result": {
                                "pdf_filename": pdf_path.name,
                                "status": "FAILED",
                                "total_pages": 0,
                                "processed_pages": 0,
                                "duration_sec": 0.0,
                                "error_message": str(e)
                            }
                        })
            else:
                import multiprocessing
                from concurrent.futures import ProcessPoolExecutor, as_completed

                manager = multiprocessing.Manager()
                mp_queue = manager.Queue()

                def mp_listener():
                    while True:
                        try:
                            item = mp_queue.get(timeout=0.1)
                            if item is None:
                                break
                            progress_callback(
                                item["pdf_filename"],
                                item["current_page"],
                                item["total_pages"],
                                item["status_msg"]
                            )
                        except Exception:
                            if not self.is_processing and mp_queue.empty():
                                break

                listener_thread = threading.Thread(target=mp_listener, daemon=True)
                listener_thread.start()

                try:
                    with ProcessPoolExecutor(max_workers=num_workers) as executor:
                        futures = {executor.submit(_worker_process_single_pdf, pdf, config_dict, mp_queue): pdf for pdf in target_pdfs}
                        for future in as_completed(futures):
                            if self.stop_requested:
                                break
                            try:
                                res = future.result()
                                total_processed_pages += res.get("processed_pages", 0)
                                completed_pdfs_count += 1
                                self.msg_queue.put({"type": "PDF_FINISHED", "result": res})
                            except Exception as e:
                                pdf_obj = futures[future]
                                self.logger.error(f"Worker exception for {pdf_obj.name}: {e}")
                                self.state_mgr.mark_failed(pdf_obj.name, str(e))
                                self.msg_queue.put({
                                    "type": "PDF_FINISHED",
                                    "result": {
                                        "pdf_filename": pdf_obj.name,
                                        "status": "FAILED",
                                        "total_pages": 0,
                                        "processed_pages": 0,
                                        "duration_sec": 0.0,
                                        "error_message": str(e)
                                    }
                                })
                finally:
                    mp_queue.put(None)
                    listener_thread.join(timeout=1.0)
                    try:
                        manager.shutdown()
                    except Exception:
                        pass
        finally:
            self.msg_queue.put({"type": "BATCH_COMPLETE", "total_elapsed": time.time() - start_batch_time})

    def _process_queue_messages(self):
        """Polls message queue from background thread to update Tkinter UI elements safely."""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                m_type = msg.get("type")

                if m_type == "PROGRESS":
                    self.progress_card.update_progress(
                        msg["pdf_filename"],
                        msg["current_page"],
                        msg["total_pages"],
                        msg["pdf_index"],
                        msg["total_pdfs"],
                        msg["status_msg"],
                        msg["elapsed"],
                        msg["remaining"]
                    )
                    iso, _ = extract_newspaper_date(msg["pdf_filename"])
                    self.review_table.update_item(
                        msg["pdf_filename"],
                        iso or "DATE UNKNOWN",
                        msg["total_pages"],
                        msg["current_page"],
                        "PROCESSING",
                        self.cmb_lang.get(),
                        msg["elapsed"]
                    )
                    self._update_summary_counts()

                elif m_type == "PDF_FINISHED":
                    res = msg["result"]
                    filename = res["pdf_filename"]
                    status = res["status"]

                    # Automatic REDO move for FAILED PDFs
                    if status == "FAILED":
                        target_path = None
                        for p in self.selected_pdfs:
                            if p.name == filename:
                                target_path = p
                                break
                        if target_path and target_path.exists():
                            try:
                                redo_dir = DIRS["redo"]
                                redo_dir.mkdir(parents=True, exist_ok=True)
                                dest_path = redo_dir / filename
                                if dest_path.exists():
                                    sha256 = res.get("sha256") or calculate_sha256(target_path)
                                    short_h = sha256[:8]
                                    dest_path = redo_dir / f"{target_path.stem}_{short_h}.pdf"
                                shutil.move(str(target_path), str(dest_path))
                                self.logger.info(f"Automatically moved FAILED PDF '{filename}' to {dest_path}")
                            except Exception as e:
                                self.logger.error(f"Failed to automatically move FAILED PDF '{filename}' to redo: {e}")

                    self.review_table.update_item(
                        res["pdf_filename"],
                        res.get("date_extracted") or "DATE UNKNOWN",
                        res["total_pages"],
                        res["processed_pages"],
                        res["status"],
                        self.cmb_lang.get(),
                        res["duration_sec"]
                    )
                    self._update_summary_counts()
                    
                    total_cnt = len(self.selected_pdfs)
                    completed_count = sum(1 for item in self.review_table.tree.get_children()
                                          if self.review_table.tree.item(item)["values"][4] in ["SUCCESS", "FAILED", "NEEDS REVIEW", "DUPLICATE"])
                    self.progress_card.update_progress(
                        filename=res["pdf_filename"],
                        current_page=res["processed_pages"],
                        total_pages=res["total_pages"],
                        pdf_index=completed_count,
                        total_pdfs=total_cnt,
                        status_msg=f"Finished '{res['pdf_filename']}' ({res['status']})",
                        elapsed_sec=res.get("duration_sec", 0)
                    )



                elif m_type == "BATCH_COMPLETE":
                    self.is_processing = False
                    self.btn_start.config(state="normal")
                    self.btn_stop.config(state="disabled")
                    self.cmb_lang.config(state="readonly")
                    self.btn_dup_check.config(state="normal")
                    
                    self._update_summary_counts()

                    succ = 0
                    dup = 0
                    rev = 0
                    fail = 0
                    pend = 0

                    for item in self.review_table.tree.get_children():
                        values = self.review_table.tree.item(item)["values"]
                        status = values[4]
                        if status == "SUCCESS":
                            succ += 1
                        elif status == "DUPLICATE":
                            dup += 1
                        elif status == "NEEDS REVIEW":
                            rev += 1
                        elif status == "FAILED":
                            fail += 1
                        else:
                            pend += 1

                    total_cnt = len(self.selected_pdfs)
                    header_str = "BATCH STOPPED" if self.stop_requested else "BATCH COMPLETE"
                    status_str = "Batch stopped" if self.stop_requested else "Batch completed"
                    self.progress_card.lbl_status.config(text=f"Status: {status_str}")
                    if not self.stop_requested:
                        self.progress_card.lbl_file.config(text="Current PDF: None / Batch completed")
                        if hasattr(self, "btn_combine"):
                            self.btn_combine.config(state="normal")
                    else:
                        if hasattr(self, "btn_combine"):
                            self.btn_combine.config(state="disabled")

                    summary_msg = (
                        f"========== {header_str} ==========\n\n"
                        f"Total PDFs       : {total_cnt}\n"
                        f"Successful       : {succ}\n"
                        f"Failed           : {fail}\n"
                        f"Needs Review     : {rev}\n"
                        f"Duplicates       : {dup}\n"
                        f"Pending          : {pend}\n"
                        f"TXT Created      : {succ}\n\n"
                        f"====================================="
                    )
                    messagebox.showinfo(header_str.title(), summary_msg)


        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_queue_messages)

    def _on_table_row_selected(self, row_values):
        filename = row_values[0]
        status = row_values[4]
        if status in ["FAILED", "NEEDS REVIEW", "DUPLICATE"]:
            info = self.state_mgr.get_file_state(filename)
            err_msg = info.get("error_message", "No details available.")
            messagebox.showinfo(f"PDF Details - {status}", f"File: {filename}\nStatus: {status}\nDate: {row_values[1]}\n\nDetails:\n{err_msg}")

    def _open_extracted_text_folder(self):
        folder = str(DIRS["extracted_text"])
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def _open_redo_folder(self):
        folder = str(DIRS["redo"])
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def _open_combined_folder(self):
        folder = str(DIRS["combined"])
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def _open_logs_folder(self):
        folder = str(DIRS["logs"])
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def _combine_all_text(self):
        batch_pdfs = getattr(self, "current_batch_pdfs", None)
        if not batch_pdfs:
            batch_pdfs = getattr(self, "selected_pdfs", None)

        success, count, out_path, msg = combine_all_text_files(pdf_list=batch_pdfs)
        if success:
            out_file_name = Path(out_path).name
            rel_path = f"Newspaper_OCR_Processor\\combined\\{out_file_name}"
            summary_msg = (
                "COMBINATION COMPLETE\n\n"
                f"{count} TXT files combined.\n\n"
                "Saved to:\n"
                f"{rel_path}\n\n"
                "Ready for manual Cloud AI upload."
            )
            messagebox.showinfo("Combination Complete", summary_msg)
            if os.path.exists(out_path):
                os.startfile(out_path)
        else:
            if msg == "NO TEXT FILES AVAILABLE":
                messagebox.showwarning("NO TEXT FILES AVAILABLE", "There are no successful OCR TXT files to combine.")
            else:
                messagebox.showwarning("NO TEXT FILES TO COMBINE", msg)






    def _open_settings(self):
        dlg = SettingsDialog(self, self.cfg_mgr, on_save_callback=self._on_settings_saved)
        self.wait_window(dlg)

    def _on_settings_saved(self, new_config):
        self._refresh_language_dropdown()
        messagebox.showinfo("Settings Saved", "Application settings updated successfully.")
