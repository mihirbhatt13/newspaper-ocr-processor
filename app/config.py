import os
import json
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Base directories strictly within the project folder
DIRS = {
    "pdfs": PROJECT_ROOT / "pdfs",
    "unique": PROJECT_ROOT / "unique",
    "duplicates": PROJECT_ROOT / "duplicates",
    "extracted_text": PROJECT_ROOT / "extracted_text",
    "redo": PROJECT_ROOT / "redo",
    "failed": PROJECT_ROOT / "failed",
    "combined": PROJECT_ROOT / "combined",
    "logs": PROJECT_ROOT / "logs",
    "config": PROJECT_ROOT / "config",
}



CONFIG_FILE = DIRS["config"] / "app_config.json"

DEFAULT_LANG_MAP = {
    "Auto": "Auto",
    "English": "eng",
    "Hindi": "hin",
    "Gujarati": "guj",
    "Marathi": "mar",
    "Tamil": "tam",
    "Telugu": "tel",
    "Bengali": "ben",
    "Kannada": "kan",
    "Malayalam": "mal",
    "Punjabi": "pan",
    "Odia": "ori",
    "Urdu": "urd",
}

COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]

COMMON_POPPLER_PATHS = [
    r"C:\Program Files\poppler\poppler-26.02.0\Library\bin",
    r"C:\Program Files\poppler\bin",
    r"C:\poppler\bin",
    r"C:\poppler-24.08.0\Library\bin",
]

def ensure_directories():
    """Ensure all required project directories exist."""
    for d in DIRS.values():
        d.mkdir(parents=True, exist_ok=True)

def find_tesseract():
    """Find installed tesseract.exe executable."""
    cmd = shutil.which("tesseract")
    if cmd and os.path.exists(cmd):
        return cmd
    for path in COMMON_TESSERACT_PATHS:
        if os.path.exists(path):
            return path
    return ""

def find_poppler():
    """Find installed Poppler bin directory containing pdftoppm.exe."""
    cmd = shutil.which("pdftoppm")
    if cmd:
        return os.path.dirname(cmd)
    for path in COMMON_POPPLER_PATHS:
        pdftoppm = os.path.join(path, "pdftoppm.exe")
        if os.path.exists(pdftoppm):
            return path
    return ""

def get_installed_tesseract_languages(tesseract_cmd=None):
    """Detect available Tesseract language codes on system."""
    if not tesseract_cmd:
        tesseract_cmd = find_tesseract()
    if not tesseract_cmd or not os.path.exists(tesseract_cmd):
        return []
    
    # Try running tesseract --list-langs
    try:
        res = subprocess.run([tesseract_cmd, "--list-langs"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            # First line is usually "List of available languages..."
            langs = [line.strip() for line in lines if line.strip() and not line.startswith("List")]
            return sorted(langs)
    except Exception:
        pass

    # Fallback: check tessdata directory next to tesseract.exe or standard path
    tessdata_dir = os.path.join(os.path.dirname(tesseract_cmd), "tessdata")
    if not os.path.exists(tessdata_dir):
        tessdata_dir = r"C:\Program Files\Tesseract-OCR\tessdata"
    
    if os.path.exists(tessdata_dir):
        langs = []
        for f in os.listdir(tessdata_dir):
            if f.endswith(".traineddata"):
                langs.append(f[:-12])
        return sorted(langs)
    return []

class ConfigManager:
    """Manages application settings."""
    def __init__(self):
        ensure_directories()
        self.config = self.load_config()

    def load_config(self):
        default_tess = find_tesseract()
        default_popp = find_poppler()
        
        defaults = {
            "tesseract_cmd": default_tess,
            "poppler_path": default_popp,
            "ocr_workers": 2,
            "dpi": 200,
            "ocr_language": "Auto",
            "custom_languages": [],
        }

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception:
                pass
        
        # Save back to make sure config file exists with complete keys
        self.save_config(defaults)
        return defaults

    def save_config(self, new_config=None):
        if new_config:
            self.config = new_config
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
