import os
import logging
from datetime import datetime
from app.config import DIRS

def setup_logger():
    DIRS["logs"].mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = DIRS["logs"] / f"ocr_{today}.log"

    logger = logging.getLogger("NewspaperOCR")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # File Handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(file_formatter)
        logger.addHandler(fh)

        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
        ch.setFormatter(console_formatter)
        logger.addHandler(ch)

    return logger

def get_logger():
    return setup_logger()
