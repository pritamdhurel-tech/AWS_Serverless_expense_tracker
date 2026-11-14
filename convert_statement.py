
import csv
from pathlib import Path

from src.expense_processor import parse_monthly_statement_text


def main():
    project_folder = Path(__file__).parent

    input_file = (
        project_folder / "data" / "extracted_statement.txt"
    )

    output_file = (
        project_folder / "data" / "converted_statement.csv"
    )

    try:
        # Parse the extracted monthly statement
        result = parse_monthly_statement_text(input_file)

        # Write transactions in the AWS Lambda CSV format
        columns = [
            "S.N",
            "Transaction Date",
            "Description",
            "Withdraw",
            "Deposit",
            "Balance"
        ]

        with open(
            output_file,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=columns
            )

            writer.writeheader()

            for transaction in result["transactions"]:
                writer.writerow({
                    "S.N": transaction["S.N"],
                    "Transaction Date": transaction["date"],
                    "Description": transaction["description"],
                    "Withdraw": transaction["withdraw"],
                    "Deposit": transaction["deposit"],
                    "Balance": transaction["balance"]
                })

        print("\nPDF TO CSV CONVERSION SUCCESSFUL")
        print("--------------------------------")
        print("Transactions:", result["transaction_count"])
        print("Total Credit:", result["total_credit"])
        print("Total Debit:", result["total_debit"])
        print("Closing Balance:", result["closing_balance"])
        print("CSV saved to:", output_file)

    except Exception as error:
        print("Conversion failed:", error)


if __name__ == "__main__":
    main()
