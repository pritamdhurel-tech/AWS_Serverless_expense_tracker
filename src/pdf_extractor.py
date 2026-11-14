
from pathlib import Path
from pypdf import PdfReader


def extract_pdf_text(pdf_path):
    """Extract selectable text from a PDF file."""

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Please select a PDF file.")

    reader = PdfReader(str(pdf_path))

    if reader.is_encrypted:
        raise ValueError(
            "This PDF is encrypted or password protected."
        )

    extracted_pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        if page_text and page_text.strip():
            extracted_pages.append(
                f"--- Page {page_number} ---\n{page_text}"
            )

    if not extracted_pages:
        raise ValueError(
            "No selectable text found. "
            "The PDF may require OCR."
        )

    return "\n\n".join(extracted_pages)
