import tkinter as tk
from tkinter import ttk

STATUS_COLORS = {
    "SUCCESS": ("#1b5e20", "#e8f5e9"),       # Dark Green text, Light Green bg
    "DUPLICATE": ("#4a148c", "#f3e5f5"),     # Purple text, Light Purple bg
    "NEEDS REVIEW": ("#e65100", "#fff3e0"),  # Dark Amber text, Light Amber bg
    "FAILED": ("#b71c1c", "#ffebee"),        # Dark Red text, Light Red bg
    "PROCESSING": ("#0d47a1", "#e3f2fd"),    # Dark Blue text, Light Blue bg
    "PENDING": ("#424242", "#f5f5f5")        # Gray text, Light Gray bg
}

class ReviewTable(ttk.Frame):
    """Custom Treeview table displaying PDF file status, date, page counts, language, and duration."""
    def __init__(self, parent, on_select_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_select_callback = on_select_callback

        columns = ("filename", "date", "pages", "processed", "status", "language", "duration")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("filename", text="PDF Filename")
        self.tree.heading("date", text="Date")
        self.tree.heading("pages", text="Total Pages")
        self.tree.heading("processed", text="Processed")
        self.tree.heading("status", text="Status")
        self.tree.heading("language", text="OCR Language")
        self.tree.heading("duration", text="Duration")

        self.tree.column("filename", width=240, anchor="w")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("pages", width=80, anchor="center")
        self.tree.column("processed", width=80, anchor="center")
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("language", width=110, anchor="center")
        self.tree.column("duration", width=80, anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Configure tags for status colors
        self.tree.tag_configure("SUCCESS", foreground="#1b5e20")
        self.tree.tag_configure("DUPLICATE", foreground="#4a148c")
        self.tree.tag_configure("OUT_OF_DATE", foreground="#e65100")
        self.tree.tag_configure("NEEDS_REVIEW", foreground="#e65100")
        self.tree.tag_configure("FAILED", foreground="#b71c1c")
        self.tree.tag_configure("MOVED_TO_REDO", foreground="#006064")
        self.tree.tag_configure("PROCESSING", foreground="#0d47a1")
        self.tree.tag_configure("PENDING", foreground="#616161")



        if self.on_select_callback:
            self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, event):
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            self.on_select_callback(item["values"])

    def update_item(self, filename, date_str, pages, processed, status, language, duration_sec):
        # Format status for tag
        tag = status.replace(" ", "_")
        dur_str = f"{duration_sec:.1f}s" if duration_sec > 0 else "--"

        # Check if row exists
        existing_id = None
        for item in self.tree.get_children():
            if self.tree.item(item)["values"][0] == filename:
                existing_id = item
                break

        values = (filename, date_str or "DATE UNKNOWN", pages, processed, status, language, dur_str)

        if existing_id:
            self.tree.item(existing_id, values=values, tags=(tag,))
        else:
            self.tree.insert("", "end", values=values, tags=(tag,))

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

class ProgressCard(ttk.LabelFrame):
    """Live progress display card showing current PDF, page counters, and visual progress bars."""
    def __init__(self, parent, title="Live OCR Progress", **kwargs):
        super().__init__(parent, text=title, padding=12, **kwargs)

        f_top = ttk.Frame(self)
        f_top.pack(fill="x", pady=(0, 4))

        self.lbl_overall = ttk.Label(f_top, text="Overall PDFs: 0 / 0", font=("Segoe UI", 9, "bold"), foreground="#0d47a1")
        self.lbl_overall.pack(side="left")

        self.lbl_file = ttk.Label(self, text="Current PDF: None Selected", font=("Segoe UI", 10, "bold"))
        self.lbl_file.pack(anchor="w", pady=(0, 2))

        self.lbl_page = ttk.Label(self, text="Current Page: 0 / 0", font=("Segoe UI", 9))
        self.lbl_page.pack(anchor="w", pady=(0, 6))

        # PDF Page Progress Bar
        self.lbl_pdf_progress = ttk.Label(self, text="PDF Progress: 0 / 0", font=("Segoe UI", 8))
        self.lbl_pdf_progress.pack(anchor="w", pady=(0, 2))

        self.pbar_pdf = ttk.Progressbar(self, orient="horizontal", mode="determinate", style="Blue.Horizontal.TProgressbar")
        self.pbar_pdf.pack(fill="x", pady=(0, 6))

        # Batch Progress Bar
        self.lbl_batch_progress = ttk.Label(self, text="Batch Progress: 0 / 0 PDFs", font=("Segoe UI", 8))
        self.lbl_batch_progress.pack(anchor="w", pady=(0, 2))

        self.pbar_batch = ttk.Progressbar(self, orient="horizontal", mode="determinate", style="Green.Horizontal.TProgressbar")
        self.pbar_batch.pack(fill="x", pady=(0, 6))


        # Status & Time
        info_frame = ttk.Frame(self)
        info_frame.pack(fill="x")

        self.lbl_status = ttk.Label(info_frame, text="Status: Ready", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side="left")

        self.lbl_time = ttk.Label(info_frame, text="Elapsed: 00:00 | Remaining: --:--", font=("Segoe UI", 9))
        self.lbl_time.pack(side="right")

    def update_progress(self, filename, current_page, total_pages, pdf_index, total_pdfs, status_msg="Processing...", elapsed_sec=0, remaining_sec=None):
        self.lbl_overall.config(text=f"Overall PDFs: {pdf_index} / {total_pdfs}")
        self.lbl_file.config(text=f"Current PDF: {filename}")
        self.lbl_page.config(text=f"Current Page: {current_page} / {total_pages}")
        
        # Calculate PDF page percentage
        if total_pages > 0:
            pdf_pct = (current_page / total_pages) * 100
            self.pbar_pdf["value"] = pdf_pct
            self.lbl_pdf_progress.config(text=f"PDF Progress: {current_page} / {total_pages} ({int(pdf_pct)}%)")
        else:
            self.pbar_pdf["value"] = 0
            self.lbl_pdf_progress.config(text="PDF Progress: 0 / 0")

        # Calculate Batch percentage
        if total_pdfs > 0:
            batch_pct = (pdf_index / total_pdfs) * 100
            self.pbar_batch["value"] = batch_pct
            self.lbl_batch_progress.config(text=f"Batch Progress: {pdf_index} / {total_pdfs} PDFs ({int(batch_pct)}%)")
        else:
            self.pbar_batch["value"] = 0
            self.lbl_batch_progress.config(text="Batch Progress: 0 / 0 PDFs")

        if status_msg == "Processing...":
            status_text = f"Status: OCR processing page {current_page} / {total_pages}..."
        else:
            status_text = f"Status: {status_msg}"
            
        self.lbl_status.config(text=status_text)

        # Format elapsed and remaining time
        el_m, el_s = divmod(int(elapsed_sec), 60)
        time_str = f"Elapsed: {el_m:02d}:{el_s:02d}"
        if remaining_sec is not None and remaining_sec >= 0:
            rm_m, rm_s = divmod(int(remaining_sec), 60)
            time_str += f" | Est. Remaining: {rm_m:02d}:{rm_s:02d}"
        else:
            time_str += " | Est. Remaining: --:--"
            
        self.lbl_time.config(text=time_str)

    def reset(self):
        self.lbl_overall.config(text="Overall PDFs: 0 / 0")
        self.lbl_file.config(text="Current PDF: None Selected")
        self.lbl_page.config(text="Current Page: 0 / 0")
        self.pbar_pdf["value"] = 0
        self.pbar_batch["value"] = 0
        self.lbl_pdf_progress.config(text="PDF Progress: 0 / 0")
        self.lbl_batch_progress.config(text="Batch Progress: 0 / 0 PDFs")

        self.lbl_status.config(text="Status: Ready")
        self.lbl_time.config(text="Elapsed: 00:00 | Remaining: --:--")

class DuplicateTable(ttk.Frame):
    """Custom Treeview table displaying detected duplicate PDFs, newspaper title, date, original match, short hash, and status."""
    def __init__(self, parent, on_select_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_select_callback = on_select_callback

        columns = ("filename", "newspaper", "date", "duplicate_of", "sha256", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("filename", text="Filename")
        self.tree.heading("newspaper", text="Newspaper")
        self.tree.heading("date", text="Date")
        self.tree.heading("duplicate_of", text="Duplicate Of")
        self.tree.heading("sha256", text="SHA-256")
        self.tree.heading("status", text="Status")

        self.tree.column("filename", width=220, anchor="w")
        self.tree.column("newspaper", width=140, anchor="w")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("duplicate_of", width=200, anchor="w")
        self.tree.column("sha256", width=120, anchor="center")
        self.tree.column("status", width=90, anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("DUPLICATE", foreground="#4a148c")

        if self.on_select_callback:
            self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, event):
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            self.on_select_callback(item["values"])

    def update_item(self, filename, newspaper, date_str, duplicate_of, sha256_hash, status="DUPLICATE"):
        short_hash = sha256_hash[:12] + "..." if (sha256_hash and len(sha256_hash) > 12) else (sha256_hash or "--")
        existing_id = None
        for item in self.tree.get_children():
            if self.tree.item(item)["values"][0] == filename:
                existing_id = item
                break

        values = (filename, newspaper or "UNKNOWN NEWSPAPER", date_str or "DATE UNKNOWN", duplicate_of or "--", short_hash, status)
        if existing_id:
            self.tree.item(existing_id, values=values, tags=("DUPLICATE",))
        else:
            self.tree.insert("", "end", values=values, tags=("DUPLICATE",))

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)


