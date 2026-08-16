import os
from pathlib import Path

def get_pdf_page_count(pdf_path, poppler_path=None):
    """Fast PDF page count using pypdfium2 with pypdf fallback."""
    pdf_path = str(pdf_path)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Try pypdfium2 first (lightning fast, pure C++ pdfium)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        count = len(pdf)
        pdf.close()
        return count
    except Exception:
        pass

    # Fallback: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception:
        pass

    # Fallback: pdfinfo via poppler
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
        return info.get("Pages", 0)
    except Exception as e:
        raise RuntimeError(f"Failed to count pages in PDF {pdf_path}: {e}")

def render_pdf_page_to_image(pdf_path, page_num, dpi=200, poppler_path=None):
    """Render a single 1-indexed PDF page directly into an in-memory PIL Image object.
    
    Uses pypdfium2 for ultra-fast C++ rendering with poppler fallback.
    """
    pdf_path = str(pdf_path)

    # 1. Primary Engine: pypdfium2 (Ultra-fast, zero subprocess deadlocks)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        if 1 <= page_num <= len(pdf):
            page = pdf[page_num - 1] # 0-indexed in pdfium
            # Render scale: 72 points per inch standard. scale = dpi / 72
            scale = dpi / 72.0
            image = page.render(scale=scale).to_pil()
            pdf.close()
            return image
        pdf.close()
    except Exception:
        pass

    # 2. Fallback Engine: pdf2image / poppler
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_num,
            last_page=page_num,
            poppler_path=poppler_path,
            thread_count=1
        )
        if images:
            return images[0]
    except Exception as e:
        raise RuntimeError(f"Error rendering page {page_num} of {Path(pdf_path).name}: {e}")

    raise RuntimeError(f"Failed to render page {page_num} of {Path(pdf_path).name}")

def is_image_blank(pil_image, threshold_pct=0.1):
    """Check if rendered PIL Image is blank/corrupt by measuring dark ink pixel percentage (< 240 threshold).
    
    Returns True if dark pixel percentage is below threshold_pct (default 0.1%).
    """
    if pil_image is None:
        return True
    try:
        gray = pil_image.convert("L")
        if hasattr(gray, "get_flattened_data"):
            pixels = gray.get_flattened_data()
        else:
            pixels = gray.getdata()
        total_pixels = len(pixels)
        if total_pixels == 0:
            return True
        dark_pixels = sum(1 for p in pixels if p < 240)
        pct = (dark_pixels / total_pixels) * 100
        return pct < threshold_pct
    except Exception:
        return True

