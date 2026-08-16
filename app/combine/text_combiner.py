import os
from pathlib import Path
from app.config import DIRS
from app.utils.date_parser import extract_newspaper_date

def combine_all_text_files(pdf_list=None, output_path=None):
    """Combines extracted text files for the specified batch (or all valid extracted text files if pdf_list is None)
    into a single file grouped chronologically by date.
    
    Returns tuple: (success, file_count, output_path, message)
    """
    ext_dir = DIRS["extracted_text"]
    if not ext_dir.exists():
        return False, 0, "", "Extracted text directory does not exist."

    if pdf_list is not None and len(pdf_list) > 0:
        valid_files = []
        for pdf_item in pdf_list:
            if isinstance(pdf_item, Path):
                stem = pdf_item.stem
            elif isinstance(pdf_item, dict):
                stem = Path(pdf_item.get("pdf_filename", "")).stem
            else:
                stem = Path(str(pdf_item)).stem
            
            txt_path = ext_dir / f"{stem}.txt"
            if txt_path.exists() and txt_path.is_file() and not txt_path.name.startswith("all_newspaper"):
                valid_files.append(txt_path)
    else:
        # Recursively find all .txt files inside extracted_text/
        all_txt_files = sorted(list(ext_dir.rglob("*.txt")))
        valid_files = [f for f in all_txt_files if not f.name.startswith("all_newspaper")]

    if not valid_files:
        return False, 0, "", "NO TEXT FILES AVAILABLE"



    if output_path is None:
        DIRS["combined"].mkdir(parents=True, exist_ok=True)
        base_name = "all_newspaper"
        target = DIRS["combined"] / f"{base_name}.txt"
        if target.exists():
            counter = 2
            while True:
                target = DIRS["combined"] / f"{base_name}{counter}.txt"
                if not target.exists():
                    break
                counter += 1
        output_path = target
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)


    # Group files by date
    # Map: date_sort_key -> (formatted_date_header, list_of_file_paths)
    date_groups = {}
    
    for f in valid_files:
        iso_date, date_label = extract_newspaper_date(f.name)
        if not iso_date:
            # Check parent folder name
            parent_name = f.parent.name
            if parent_name != "extracted_text" and parent_name != "DATE_UNKNOWN":
                iso_date, date_label = extract_newspaper_date(parent_name)
        
        sort_key = iso_date if iso_date else "9999-99-99_UNKNOWN"
        display_label = date_label if date_label else "DATE UNKNOWN"

        if sort_key not in date_groups:
            date_groups[sort_key] = (display_label, [])
        date_groups[sort_key][1].append(f)

    # Write combined output with clear date headers and newspaper headers
    with open(output_path, "w", encoding="utf-8") as out:
        first_group = True
        for sort_key in sorted(date_groups.keys()):
            display_label, files_list = date_groups[sort_key]
            
            if not first_group:
                out.write("\n\n")
            first_group = False

            out.write("==================================================\n")
            out.write(f"DATE: {display_label}\n")
            out.write("==================================================\n\n")

            for txt_file in sorted(files_list, key=lambda x: x.name):
                newspaper_title = txt_file.stem.upper().replace("_", " ")
                out.write("==================================================\n")
                out.write(f"NEWSPAPER: {newspaper_title}\n")
                out.write("==================================================\n")
                
                try:
                    with open(txt_file, "r", encoding="utf-8") as f_in:
                        content = f_in.read()
                        out.write(content.strip() + "\n\n")
                except Exception as e:
                    out.write(f"[ERROR READING FILE {txt_file.name}: {e}]\n\n")

    msg = f"Combined {len(valid_files)} newspapers into {output_path.name}"
    return True, len(valid_files), str(output_path), msg
