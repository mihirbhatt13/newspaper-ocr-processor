import sys
import os
from pathlib import Path

# Add project root to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ensure_directories, ConfigManager
from app.utils.logger import get_logger
from app.gui.main_window import MainWindow

def main():
    """Main entry point for Newspaper OCR Processor application."""
    ensure_directories()
    logger = get_logger()
    logger.info("Initializing Newspaper OCR Processor GUI Application...")

    cfg = ConfigManager().load_config()
    logger.info(f"Loaded config: Tesseract='{cfg.get('tesseract_cmd')}', Workers={cfg.get('ocr_workers')}, DPI={cfg.get('dpi')}")

    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
