"""OCR text extraction service for image ingestion (.png, .jpg, .jpeg).

Implements Task 2.1:
- Uses `PIL.Image` and `pytesseract.image_to_string` to extract text from image documents.
- Gracefully handles missing `PIL`/`pytesseract` libraries, missing Tesseract system binaries,
  or unreadable image files by logging a warning and returning an empty string `""`.
"""
import os
from pathlib import Path
from typing import Union

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def extract_text_from_image(image_path: Union[str, Path]) -> str:
    """Extract text from an image file using PIL and pytesseract, with graceful fallback."""
    path_str = str(image_path)
    if not os.path.isfile(path_str):
        print(f"OCR warning: Image file not found at {path_str}")
        return ""

    try:
        from PIL import Image
        import pytesseract

        with Image.open(path_str) as image:
            extracted = pytesseract.image_to_string(image)
            return (extracted or "").strip()
    except Exception as exc:
        print(f"OCR warning: Could not extract text from {path_str}: {exc}")
        return ""

