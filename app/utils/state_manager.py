import os
import json
import threading
from pathlib import Path
from app.config import DIRS
from app.utils.file_utils import calculate_sha256
from app.utils.date_parser import extract_newspaper_date

STATE_FILE = DIRS["config"] / "state.json"
_lock = threading.RLock()

class StateManager:
    """Tracks state of OCR processing across files and pages for SHA-256 deduplication, date organizing, and resume."""
    def __init__(self):
        DIRS["config"].mkdir(parents=True, exist_ok=True)
        self.state = self.load_state()

    def load_state(self):
        with _lock:
            if STATE_FILE.exists():
                try:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "hashes" not in data:
                            data["hashes"] = {}
                        if "files" not in data:
                            data["files"] = {}
                        self.state = data
                        return data
                except Exception:
                    pass
            self.state = {"hashes": {}, "files": {}}
            return self.state


    def save_state(self):
        with _lock:
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2)
            except Exception:
                pass

    def get_file_state(self, pdf_filename, sha256_hash=None):
        with _lock:
            files_dict = self.state.get("files", {})
            if sha256_hash and sha256_hash in files_dict:
                return files_dict[sha256_hash]
            
            if not sha256_hash:
                for h, record in files_dict.items():
                    if record.get("pdf_filename") == pdf_filename:
                        return record
                    
            iso_date, _ = extract_newspaper_date(pdf_filename)
            date_dir = iso_date if iso_date else "DATE_UNKNOWN"

            # Store new TXT output directly inside extracted_text/ flat folder
            stem = Path(pdf_filename).stem
            target_out = DIRS["extracted_text"] / f"{stem}.txt"
            if sha256_hash:
                for existing_h, existing_rec in files_dict.items():
                    if existing_h != sha256_hash:
                        raw_out = existing_rec.get("output_file", "")
                        if raw_out and Path(raw_out).resolve() == target_out.resolve():
                            short_h = sha256_hash[:8]
                            target_out = DIRS["extracted_text"] / f"{stem}_{short_h}.txt"
                            break


            return {
                "pdf_filename": pdf_filename,
                "sha256": sha256_hash or "",
                "status": "PENDING",
                "total_pages": 0,
                "completed_pages": [],
                "output_file": str(target_out),
                "error_message": "",
                "duration_sec": 0.0,
                "language_used": "",
                "date_extracted": iso_date or "DATE UNKNOWN",
                "original_file": ""
            }

    def is_pdf_completed(self, pdf_filename, total_pages=None, sha256_hash=None):
        info = self.get_file_state(pdf_filename, sha256_hash=sha256_hash)
        output_file = Path(info.get("output_file", ""))
        
        if info.get("status") == "SUCCESS" and output_file.exists() and output_file.stat().st_size > 0:
            if total_pages is None or len(info.get("completed_pages", [])) >= total_pages:
                return True
        return False

    def get_completed_pages(self, pdf_filename, sha256_hash=None):
        info = self.get_file_state(pdf_filename, sha256_hash=sha256_hash)
        completed = set(info.get("completed_pages", []))
        
        output_file = Path(info.get("output_file", ""))
        if output_file and output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    for line in content.splitlines():
                        if line.startswith("--- PAGE ") and (" ---" in line):
                            try:
                                p_str = line.split("--- PAGE ")[1].split(" ---")[0].strip()
                                p_num = int(p_str.split()[0])
                                completed.add(p_num)
                            except Exception:
                                pass
            except Exception:
                pass
        return sorted(list(completed))

    def init_pdf_state(self, pdf_path, total_pages, language_used="Auto"):
        """Initializes PDF state using SHA-256 hash as primary identity."""
        with _lock:
            pdf_path = Path(pdf_path)
            pdf_filename = pdf_path.name
            sha256 = calculate_sha256(pdf_path)

            hashes_dict = self.state.setdefault("hashes", {})
            files_dict = self.state.setdefault("files", {})

            iso_date, date_label = extract_newspaper_date(pdf_filename)
            date_folder_name = iso_date if iso_date else "DATE_UNKNOWN"
            date_dir = DIRS["extracted_text"] / date_folder_name
            date_dir.mkdir(parents=True, exist_ok=True)

            # Check 1: SHA-256 Duplicate Check
            if sha256 in hashes_dict and hashes_dict[sha256] != pdf_filename:
                orig_name = hashes_dict[sha256]
                existing_out = files_dict.get(sha256, {}).get("output_file", "")
                err_msg = f"Duplicate file content (SHA-256 match with {orig_name})"
                rec = {
                    "pdf_filename": pdf_filename,
                    "sha256": sha256,
                    "status": "DUPLICATE",
                    "total_pages": total_pages,
                    "completed_pages": [],
                    "output_file": existing_out,
                    "error_message": err_msg,
                    "duration_sec": 0.0,
                    "language_used": language_used,
                    "date_extracted": iso_date or "DATE UNKNOWN",
                    "original_file": orig_name
                }
                # Keep original file record intact under sha256, don't overwrite primary file record if already SUCCESS
                if sha256 not in files_dict or files_dict[sha256].get("status") != "SUCCESS":
                    files_dict[sha256] = rec
                self.save_state()
                return rec


            # Record primary hash ownership
            hashes_dict[sha256] = pdf_filename

            # Check 2: Output file collision for different SHA-256 with same filename
            stem = pdf_path.stem
            target_out = DIRS["extracted_text"] / f"{stem}.txt"

            for existing_hash, existing_rec in list(files_dict.items()):
                if existing_hash != sha256:
                    raw_out = existing_rec.get("output_file", "")
                    if raw_out:
                        p1 = Path(raw_out).resolve()
                        p2 = target_out.resolve()
                        if p1 == p2:
                            short_h = sha256[:8]
                            target_out = DIRS["extracted_text"] / f"{stem}_{short_h}.txt"
                            break

                            break



            # Store preliminary record with unique target_out before calling get_completed_pages
            if sha256 not in files_dict:
                files_dict[sha256] = {
                    "pdf_filename": pdf_filename,
                    "sha256": sha256,
                    "status": "PENDING",
                    "total_pages": total_pages,
                    "completed_pages": [],
                    "output_file": str(target_out),
                    "error_message": "",
                    "duration_sec": 0.0,
                    "language_used": language_used,
                    "date_extracted": iso_date or "DATE UNKNOWN",
                    "original_file": ""
                }
            else:
                files_dict[sha256]["output_file"] = str(target_out)

            self.save_state()

            completed_pages = self.get_completed_pages(pdf_filename, sha256_hash=sha256)
            existing_rec = files_dict[sha256]
            curr_status = existing_rec.get("status", "PENDING")
            if curr_status not in ["NEEDS REVIEW", "FAILED", "DUPLICATE"]:
                status = "SUCCESS" if (len(completed_pages) == total_pages and total_pages > 0) else "PENDING"
            else:
                status = curr_status

            rec = {
                "pdf_filename": pdf_filename,
                "sha256": sha256,
                "status": status,
                "total_pages": total_pages,
                "completed_pages": completed_pages,
                "output_file": str(target_out),
                "error_message": existing_rec.get("error_message", ""),
                "duration_sec": existing_rec.get("duration_sec", 0.0),
                "language_used": language_used,
                "date_extracted": iso_date or "DATE UNKNOWN",
                "original_file": ""
            }

            files_dict[sha256] = rec
            self.save_state()
            return rec

    def append_page_text(self, pdf_filename, page_num, total_pages, text_content, language_used="Auto", sha256_hash=None):
        with _lock:
            info = self.get_file_state(pdf_filename, sha256_hash=sha256_hash)
            sha256 = info.get("sha256") or sha256_hash
            
            completed_pages = set(info.get("completed_pages", []))
            output_path = Path(info["output_file"])
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if page_num not in completed_pages:
                header = f"--- PAGE {page_num} ---\n"
                footer = "\n\n"
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(header + text_content.strip() + footer)
                completed_pages.add(page_num)

            info["completed_pages"] = sorted(list(completed_pages))
            info["total_pages"] = total_pages
            info["language_used"] = language_used
            
            if info.get("status") not in ["NEEDS REVIEW", "FAILED", "DUPLICATE"]:
                if len(info["completed_pages"]) >= total_pages and total_pages > 0:
                    info["status"] = "SUCCESS"
                else:
                    info["status"] = "PROCESSING"

            if sha256:
                self.state.setdefault("files", {})[sha256] = info
            self.save_state()

    def mark_failed(self, pdf_filename, error_message, total_pages=0, sha256_hash=None):
        with _lock:
            info = self.get_file_state(pdf_filename, sha256_hash=sha256_hash)
            sha256 = info.get("sha256") or sha256_hash
            info["status"] = "FAILED"
            info["error_message"] = str(error_message)
            if total_pages > 0:
                info["total_pages"] = total_pages
            if sha256:
                self.state.setdefault("files", {})[sha256] = info
            self.save_state()

    def mark_needs_review(self, pdf_filename, reason_message, total_pages=0, sha256_hash=None):
        with _lock:
            info = self.get_file_state(pdf_filename, sha256_hash=sha256_hash)
            sha256 = info.get("sha256") or sha256_hash
            info["status"] = "NEEDS REVIEW"
            info["error_message"] = str(reason_message)
            if total_pages > 0:
                info["total_pages"] = total_pages
            if sha256:
                self.state.setdefault("files", {})[sha256] = info
            self.save_state()

    def update_duration(self, pdf_filename, duration_sec, sha256_hash=None):
        with _lock:
            info = self.get_file_state(pdf_filename, sha256_hash=sha256_hash)
            sha256 = info.get("sha256") or sha256_hash
            info["duration_sec"] = round(duration_sec, 2)
            if sha256:
                self.state.setdefault("files", {})[sha256] = info
            self.save_state()
