import time
import os
import hashlib
from pathlib import Path

def calculate_sha256(file_path, chunk_size=65536):
    """Calculates SHA-256 hash of a file in streaming chunks."""
    fpath = Path(file_path)
    if not fpath.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hasher = hashlib.sha256()
    with open(fpath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()

def safe_remove_file(file_path, max_retries=5, delay_sec=0.1):
    """Safely removes a temporary file with retry backoff to prevent Windows [WinError 32] lock failures."""
    if not file_path:
        return True
    fpath = Path(file_path)
    for attempt in range(max_retries):
        try:
            if fpath.exists():
                fpath.unlink()
            return True
        except (PermissionError, OSError):
            if attempt < max_retries - 1:
                time.sleep(delay_sec)
    return False

