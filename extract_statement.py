
import re
from pathlib import Path
from tkinter import Tk, filedialog

from src.pdf_extractor import extract_pdf_text
from src.expense_processor import export_statement_to_csv


def main():
    root = Tk()
    root.withdraw()

    pdf_path = filedialog.askopenfilename(
        title="Select Monthly Bank Statement",
        filetypes=[("PDF files", "*.pdf")]
    )

    root.destroy()

    if not pdf_path:
        print("No PDF selected.")
        return

    project_folder = Path(__file__).parent

    text_file = project_folder / "data" / "extracted_statement.txt"
    csv_file = project_folder / "data" / "converted_statement.csv"

    try:
        # STEP 1: Extract PDF text
        extracted_text = extract_pdf_text(pdf_path)

        # STEP 2: Redact sensitive account information
        extracted_text = re.sub(
            r"(?im)(Account Holder\s*\n)\s*.*",
            r"\1[REDACTED]",
            extracted_text
        )

        extracted_text = re.sub(
            r"(?im)(Account Number\s*\n)\s*.*",
            r"\1[REDACTED]",
            extracted_text
        )

        # STEP 3: Save extracted text
        text_file.parent.mkdir(parents=True, exist_ok=True)

        text_file.write_text(
            extracted_text,
            encoding="utf-8"
        )

        print("\nPDF TEXT EXTRACTION SUCCESSFUL")
        print("Saved:", text_file)

        # STEP 4: Convert extracted text into CSV
        summary = export_statement_to_csv(
            text_file,
            csv_file
        )

        print("\nCSV CONVERSION SUCCESSFUL")
        print("-------------------------")
        print("Opening Balance:", summary["opening_balance"])
        print("Total Credit:", summary["total_credit"])
        print("Total Debit:", summary["total_debit"])
        print("Closing Balance:", summary["closing_balance"])
        print("Transactions:", summary["transaction_count"])
        print("CSV Saved:", summary["output_file"])

    except Exception as error:
        print("\nStatement processing failed:", error)


if __name__ == "__main__":
    main()
