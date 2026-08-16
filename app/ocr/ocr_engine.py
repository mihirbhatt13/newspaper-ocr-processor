import os
import tempfile
import pytesseract
from app.config import get_installed_tesseract_languages, DEFAULT_LANG_MAP
from app.utils.file_utils import safe_remove_file

class OCREngine:
    """Tesseract OCR execution engine with language validation and error reporting."""
    def __init__(self, tesseract_cmd=None):
        self.tesseract_cmd = tesseract_cmd
        self._cached_installed = None
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            
    def get_installed_languages(self):
        if self._cached_installed is None:
            self._cached_installed = get_installed_tesseract_languages(self.tesseract_cmd)
        return self._cached_installed

    def validate_languages(self, lang_setting):
        """Validate if requested language code/combination is available in Tesseract.
        
        Returns tuple: (is_valid, resolved_lang_code, missing_languages)
        """
        installed = set(self.get_installed_languages())
        
        if lang_setting == "Auto" or not lang_setting:
            if "hin" in installed and "eng" in installed:
                return True, "hin+eng", []
            elif "eng" in installed:
                return True, "eng", []
            elif installed:
                return True, list(installed)[0], []
            return False, "", ["eng"]

        requested_codes = []
        
        if lang_setting in DEFAULT_LANG_MAP and DEFAULT_LANG_MAP[lang_setting] != "Auto":
            requested_codes = [DEFAULT_LANG_MAP[lang_setting]]
        elif "+" in lang_setting:
            parts = [p.strip() for p in lang_setting.split("+")]
            for p in parts:
                code = DEFAULT_LANG_MAP.get(p, p)
                requested_codes.append(code)
        else:
            requested_codes = [DEFAULT_LANG_MAP.get(lang_setting, lang_setting)]

        missing = [code for code in requested_codes if code not in installed]
        if missing:
            return False, "+".join(requested_codes), missing

        return True, "+".join(requested_codes), []

    def perform_ocr(self, pil_image, lang_setting="Auto", extra_config="--psm 3"):
        """Run OCR on a PIL Image object with Windows file locking protection."""
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            
        valid, lang_code, missing = self.validate_languages(lang_setting)
        if not valid:
            missing_str = ", ".join([f"'{m}.traineddata'" for m in missing])
            raise ValueError(f"Required Tesseract language pack(s) missing: {missing_str}")

        # Preprocess PIL image for optimal newsprint OCR
        try:
            from PIL import ImageOps
            if pil_image.mode != "L":
                ocr_image = pil_image.convert("L")
            else:
                ocr_image = pil_image
            ocr_image = ImageOps.autocontrast(ocr_image)
        except Exception:
            ocr_image = pil_image

        # Save image to explicit temporary PNG file to avoid pytesseract's un-retried cleanup [WinError 32]
        temp_img_fd, temp_img_path = tempfile.mkstemp(suffix=".png")
        try:
            os.close(temp_img_fd)
            ocr_image.save(temp_img_path, format="PNG")
            text = pytesseract.image_to_string(temp_img_path, lang=lang_code, config=extra_config)
            
            # Fallback to single text block mode (--psm 6) if automatic segmentation (--psm 3) returns sparse text
            if len(text.strip()) < 20 and extra_config == "--psm 3":
                fallback_text = pytesseract.image_to_string(temp_img_path, lang=lang_code, config="--psm 6")
                if len(fallback_text.strip()) > len(text.strip()):
                    text = fallback_text

            return text
        finally:
            safe_remove_file(temp_img_path)


