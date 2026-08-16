import os
import multiprocessing
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from app.config import ConfigManager, find_tesseract, find_poppler, get_installed_tesseract_languages, DEFAULT_LANG_MAP

class SettingsDialog(tk.Toplevel):
    """Settings modal dialog for configuring paths, OCR resolution, worker count, and default languages."""
    def __init__(self, parent, config_manager, on_save_callback=None):
        super().__init__(parent)
        self.title("Newspaper OCR Processor - Settings")
        self.geometry("620x520")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.cfg_mgr = config_manager
        self.on_save_callback = on_save_callback
        self.config_data = dict(self.cfg_mgr.config)

        self._build_ui()
        self.center_on_parent(parent)

    def center_on_parent(self, parent):
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _build_ui(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        # Title
        lbl_title = ttk.Label(container, text="Application Settings", font=("Segoe UI", 12, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 12))

        # --- Section 1: Paths ---
        sec_paths = ttk.LabelFrame(container, text="External Tools Paths", padding=10)
        sec_paths.pack(fill="x", pady=(0, 10))

        # Tesseract Path
        ttk.Label(sec_paths, text="Tesseract Executable (tesseract.exe):").pack(anchor="w")
        f_tess = ttk.Frame(sec_paths)
        f_tess.pack(fill="x", pady=(2, 8))
        self.ent_tess = ttk.Entry(f_tess)
        self.ent_tess.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.ent_tess.insert(0, self.config_data.get("tesseract_cmd", ""))
        
        btn_tess_browse = ttk.Button(f_tess, text="Browse...", command=self._browse_tesseract)
        btn_tess_browse.pack(side="left", padx=(0, 4))
        btn_tess_auto = ttk.Button(f_tess, text="Auto-Detect", command=self._autodetect_tesseract)
        btn_tess_auto.pack(side="left")

        # Poppler Path
        ttk.Label(sec_paths, text="Poppler Bin Directory (containing pdftoppm.exe):").pack(anchor="w")
        f_popp = ttk.Frame(sec_paths)
        f_popp.pack(fill="x", pady=(2, 4))
        self.ent_popp = ttk.Entry(f_popp)
        self.ent_popp.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.ent_popp.insert(0, self.config_data.get("poppler_path", ""))

        btn_popp_browse = ttk.Button(f_popp, text="Browse...", command=self._browse_poppler)
        btn_popp_browse.pack(side="left", padx=(0, 4))
        btn_popp_auto = ttk.Button(f_popp, text="Auto-Detect", command=self._autodetect_poppler)
        btn_popp_auto.pack(side="left")

        # --- Section 2: Performance & OCR Defaults ---
        sec_perf = ttk.LabelFrame(container, text="Performance & Advanced OCR Settings", padding=10)
        sec_perf.pack(fill="x", pady=(0, 12))

        # Worker Count
        f_work = ttk.Frame(sec_perf)
        f_work.pack(fill="x", pady=4)
        ttk.Label(f_work, text="Parallel Worker Processes (Default: 2):").pack(side="left")
        max_cpus = max(1, multiprocessing.cpu_count())
        self.spn_workers = ttk.Spinbox(f_work, from_=1, to=max_cpus, width=6)
        self.spn_workers.pack(side="right")
        self.spn_workers.set(self.config_data.get("ocr_workers", 2))

        # DPI
        f_dpi = ttk.Frame(sec_perf)
        f_dpi.pack(fill="x", pady=4)
        ttk.Label(f_dpi, text="OCR Image Resolution DPI (Default: 200 DPI):").pack(side="left")
        self.spn_dpi = ttk.Spinbox(f_dpi, from_=150, to=300, increment=25, width=6)
        self.spn_dpi.pack(side="right")
        self.spn_dpi.set(self.config_data.get("dpi", 200))

        # Default Language
        f_lang = ttk.Frame(sec_perf)
        f_lang.pack(fill="x", pady=4)
        ttk.Label(f_lang, text="Default OCR Language:").pack(side="left")

        installed_langs = set(get_installed_tesseract_languages(self.config_data.get("tesseract_cmd")))
        lang_options = ["Auto"]
        for ui_name, code in DEFAULT_LANG_MAP.items():
            if ui_name == "Auto":
                continue
            if code in installed_langs:
                lang_options.append(ui_name)
            else:
                lang_options.append(f"{ui_name} [Unavailable]")

        self.cmb_lang = ttk.Combobox(f_lang, values=lang_options, state="readonly", width=22)
        self.cmb_lang.pack(side="right")
        
        curr_lang = self.config_data.get("ocr_language", "Auto")
        if curr_lang in lang_options:
            self.cmb_lang.set(curr_lang)
        else:
            self.cmb_lang.set("Auto")

        # --- Section 3: Action Buttons ---
        f_btn = ttk.Frame(container)
        f_btn.pack(fill="x", side="bottom")

        btn_save = ttk.Button(f_btn, text="Save Settings", command=self._save)
        btn_save.pack(side="right", padx=(6, 0))
        btn_cancel = ttk.Button(f_btn, text="Cancel", command=self.destroy)
        btn_cancel.pack(side="right")

    def _browse_tesseract(self):
        filename = filedialog.askopenfilename(
            title="Select tesseract.exe",
            filetypes=[("Executable", "tesseract.exe"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_tess.delete(0, tk.END)
            self.ent_tess.insert(0, filename)

    def _autodetect_tesseract(self):
        found = find_tesseract()
        if found:
            self.ent_tess.delete(0, tk.END)
            self.ent_tess.insert(0, found)
            messagebox.showinfo("Auto-Detect", f"Tesseract found:\n{found}")
        else:
            messagebox.showwarning("Auto-Detect", "Tesseract executable could not be automatically located on system.")

    def _browse_poppler(self):
        folder = filedialog.askdirectory(title="Select Poppler bin Directory")
        if folder:
            self.ent_popp.delete(0, tk.END)
            self.ent_popp.insert(0, folder)

    def _autodetect_poppler(self):
        found = find_poppler()
        if found:
            self.ent_popp.delete(0, tk.END)
            self.ent_popp.insert(0, found)
            messagebox.showinfo("Auto-Detect", f"Poppler bin folder found:\n{found}")
        else:
            messagebox.showwarning("Auto-Detect", "Poppler bin folder could not be automatically located on system.")

    def _save(self):
        tess_path = self.ent_tess.get().strip()
        popp_path = self.ent_popp.get().strip()

        if tess_path and not os.path.exists(tess_path):
            messagebox.showwarning("Warning", f"Specified Tesseract path does not exist:\n{tess_path}")

        try:
            workers = int(self.spn_workers.get())
            dpi = int(self.spn_dpi.get())
        except ValueError:
            messagebox.showerror("Error", "Workers and DPI must be valid integers.")
            return

        lang_sel = self.cmb_lang.get()
        if "[Unavailable]" in lang_sel:
            clean_lang = lang_sel.split("[")[0].strip()
            code = DEFAULT_LANG_MAP.get(clean_lang, clean_lang)
            messagebox.showwarning("Missing Language Pack", 
                                   f"The selected language '{clean_lang}' requires '{code}.traineddata' which is not installed in Tesseract.\n\nPlease install the traineddata file in Tesseract's tessdata directory.")

        self.cfg_mgr.set("tesseract_cmd", tess_path)
        self.cfg_mgr.set("poppler_path", popp_path)
        self.cfg_mgr.set("ocr_workers", workers)
        self.cfg_mgr.set("dpi", dpi)
        self.cfg_mgr.set("ocr_language", lang_sel)

        if self.on_save_callback:
            self.on_save_callback(self.cfg_mgr.config)

        self.destroy()
