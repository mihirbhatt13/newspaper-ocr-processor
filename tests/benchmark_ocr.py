import os
import sys
import time
import psutil
import threading
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ConfigManager, DIRS
from app.ocr.worker import process_pdf_file, _worker_process_single_pdf
from app.utils.state_manager import StateManager
from app.pdf.pdf_utils import get_pdf_page_count
from tests.generate_sample_pdf import create_sample_pdfs

class ResourceMonitor:
    """Monitors CPU and RAM usage during benchmark runs."""
    def __init__(self, interval=0.2):
        self.interval = interval
        self.running = False
        self.thread = None
        self.cpu_samples = []
        self.ram_samples = []
        self.process = psutil.Process(os.getpid())

    def _monitor(self):
        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram_mb = self.process.memory_info().rss / (1024 * 1024)
                self.cpu_samples.append(cpu)
                self.ram_samples.append(ram_mb)
            except Exception:
                pass
            time.sleep(self.interval)

    def start(self):
        self.running = True
        self.cpu_samples = []
        self.ram_samples = []
        psutil.cpu_percent(interval=None)
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        avg_cpu = round(sum(self.cpu_samples) / max(len(self.cpu_samples), 1), 1)
        peak_cpu = round(max(self.cpu_samples, default=0), 1)
        peak_ram = round(max(self.ram_samples, default=0), 1)
        avg_ram = round(sum(self.ram_samples) / max(len(self.ram_samples), 1), 1)
        return {
            "avg_cpu_pct": avg_cpu,
            "peak_cpu_pct": peak_cpu,
            "avg_ram_mb": avg_ram,
            "peak_ram_mb": peak_ram
        }

def clear_extracted_output():
    """Clear output folders for clean benchmark runs."""
    if DIRS["extracted_text"].exists():
        for f in DIRS["extracted_text"].glob("*.txt"):
            try:
                os.remove(f)
            except Exception:
                pass
    DIRS["extracted_text"].mkdir(parents=True, exist_ok=True)
    
    state_file = DIRS["config"] / "state.json"
    if state_file.exists():
        try:
            os.remove(state_file)
        except Exception:
            pass

def run_single_benchmark_config(config_name, pdf_files, num_workers, dpi):
    """Run benchmark for a given worker & DPI configuration."""
    clear_extracted_output()
    cfg_mgr = ConfigManager()
    
    config_dict = {
        "tesseract_cmd": cfg_mgr.get("tesseract_cmd"),
        "poppler_path": cfg_mgr.get("poppler_path"),
        "ocr_workers": num_workers,
        "dpi": dpi,
        "ocr_language": "Auto"
    }

    print(f"\n==================================================", flush=True)
    print(f"BENCHMARK CONFIG: {config_name}", flush=True)
    print(f"Workers: {num_workers} | DPI: {dpi} | Total PDFs: {len(pdf_files)}", flush=True)
    print(f"==================================================", flush=True)

    monitor = ResourceMonitor()
    monitor.start()
    
    total_start = time.time()
    results = []
    total_pages_processed = 0

    if num_workers == 1:
        for pdf_path in pdf_files:
            res = process_pdf_file(pdf_path, config_dict)
            results.append(res)
            total_pages_processed += res["total_pages"]
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_worker_process_single_pdf, pdf, config_dict): pdf for pdf in pdf_files}
            for future in as_completed(futures):
                res = future.result()
                results.append(res)
                total_pages_processed += res["total_pages"]

    total_duration = round(time.time() - total_start, 2)
    metrics = monitor.stop()

    sec_per_page = round(total_duration / max(total_pages_processed, 1), 2)
    pages_per_min = round((total_pages_processed / max(total_duration, 1)) * 60, 1)

    text_samples = []
    total_chars = 0
    for res in results:
        txt_path = Path(DIRS["extracted_text"]) / f"{Path(res['pdf_filename']).stem}.txt"
        if txt_path.exists():
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
                total_chars += len(content)
                text_samples.append(content[:150].replace('\n', ' '))

    quality_rating = "EXCELLENT" if total_chars > 3000 else ("GOOD" if total_chars > 1000 else "POOR")

    summary = {
        "config_name": config_name,
        "workers": num_workers,
        "dpi": dpi,
        "total_pdfs": len(pdf_files),
        "total_pages": total_pages_processed,
        "total_duration_sec": total_duration,
        "sec_per_page": sec_per_page,
        "pages_per_min": pages_per_min,
        "avg_cpu_pct": metrics["avg_cpu_pct"],
        "peak_cpu_pct": metrics["peak_cpu_pct"],
        "avg_ram_mb": metrics["avg_ram_mb"],
        "peak_ram_mb": metrics["peak_ram_mb"],
        "total_chars_extracted": total_chars,
        "quality_rating": quality_rating
    }

    print(f"Result: {total_duration}s total | {sec_per_page}s/page ({pages_per_min} pages/min)", flush=True)
    print(f"Resource Usage: Peak RAM = {metrics['peak_ram_mb']} MB | Avg CPU = {metrics['avg_cpu_pct']}% (Peak {metrics['peak_cpu_pct']}%)", flush=True)
    print(f"Extracted Character Count: {total_chars} chars | Quality: {quality_rating}", flush=True)

    return summary

def test_resume_functionality(sample_pdf):
    """Test page-level resume & verify zero text duplication."""
    print(f"\n--------------------------------------------------", flush=True)
    print(f"TESTING PAGE-LEVEL RESUME & DEDUPLICATION", flush=True)
    print(f"--------------------------------------------------", flush=True)

    clear_extracted_output()
    cfg_mgr = ConfigManager()
    config_dict = {
        "tesseract_cmd": cfg_mgr.get("tesseract_cmd"),
        "poppler_path": cfg_mgr.get("poppler_path"),
        "ocr_workers": 1,
        "dpi": 200,
        "ocr_language": "Auto"
    }

    pdf_filename = sample_pdf.name
    total_pages = get_pdf_page_count(sample_pdf, cfg_mgr.get("poppler_path"))
    state_mgr = StateManager()

    # Step 1: Process only 3 pages
    partial_count = min(3, total_pages)
    state_mgr.init_pdf_state(pdf_filename, total_pages)
    for p in range(1, partial_count + 1):
        state_mgr.append_page_text(pdf_filename, p, total_pages, f"Sample text for page {p}")

    txt_file = DIRS["extracted_text"] / f"{sample_pdf.stem}.txt"
    with open(txt_file, "r", encoding="utf-8") as f:
        initial_lines = f.readlines()
    print(f"Initial partial run ({partial_count} pages): {len(initial_lines)} lines written.", flush=True)

    # Step 2: Run full worker process on the same file
    res = process_pdf_file(sample_pdf, config_dict)
    
    with open(txt_file, "r", encoding="utf-8") as f:
        final_lines = f.readlines()

    page_headers = [line for line in final_lines if line.startswith("--- PAGE ")]
    duplicate_headers = len(page_headers) - len(set(page_headers))

    print(f"Resumed run result: Processed pages = {res['processed_pages']}/{total_pages} | Final total lines = {len(final_lines)}", flush=True)
    print(f"Page markers in output: {len(page_headers)} | Duplicate headers detected: {duplicate_headers}", flush=True)

    if duplicate_headers == 0 and len(page_headers) == total_pages:
        print("[PASSED] Resume deduplication test PASSED with 0 duplicate pages!", flush=True)
        return True
    else:
        print("[FAILED] Resume deduplication test FAILED.", flush=True)
        return False

def main():
    print("Generating sample newspaper PDFs for benchmark...", flush=True)
    pdf_files = create_sample_pdfs()

    configs = [
        ("1 Worker @ 200 DPI", 1, 200),
        ("2 Workers @ 200 DPI (Proposed Default)", 2, 200),
        ("2 Workers @ 150 DPI", 2, 150),
        ("2 Workers @ 300 DPI", 2, 300),
    ]

    benchmark_summaries = []
    for name, workers, dpi in configs:
        summary = run_single_benchmark_config(name, pdf_files, workers, dpi)
        benchmark_summaries.append(summary)

    # Resume test
    resume_passed = test_resume_functionality(pdf_files[0])

    print("\n==================================================", flush=True)
    print("BENCHMARK SUMMARY REPORT", flush=True)
    print("==================================================", flush=True)
    header = f"{'Configuration':<38} | {'Sec/Page':<9} | {'Pages/Min':<10} | {'Peak RAM':<10} | {'Peak CPU':<9} | {'Quality':<9}"
    print(header, flush=True)
    print("-" * len(header), flush=True)
    
    for s in benchmark_summaries:
        print(f"{s['config_name']:<38} | {s['sec_per_page']:<9} | {s['pages_per_min']:<10} | {s['peak_ram_mb']:<7} MB | {s['peak_cpu_pct']:<7} % | {s['quality_rating']:<9}", flush=True)

    return benchmark_summaries, resume_passed

if __name__ == "__main__":
    main()
