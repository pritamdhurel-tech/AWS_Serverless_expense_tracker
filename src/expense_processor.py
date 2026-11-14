
import hashlib
from datetime import datetime
from decimal import Decimal
import csv
import re

def parse_date(date_value):
    """Convert supported date formats into YYYY-MM-DD."""
    supported_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]

    for date_format in supported_formats:
        try:
            return datetime.strptime(
                date_value.strip(), date_format
            ).date().isoformat()
        except ValueError:
            continue

    raise ValueError(f"Unsupported date format: {date_value}")



def parse_amount(value):
    """Convert an amount into Decimal. Empty values become zero."""
    if value is None:
        return Decimal("0.00")

    cleaned_value = str(value).replace(",", "").strip()

    if cleaned_value == "":
        return Decimal("0.00")

    return Decimal(cleaned_value)



def normalize_transaction(row):
    """Convert one bank CSV row into a consistent transaction."""

    if not any(value and str(value).strip() for value in row.values()):
        return None

    required_fields = {"Transaction Date", "Description"}

    if not required_fields.issubset(row.keys()):
        raise ValueError("Missing required CSV columns")

    has_debit_credit = (
        "Withdraw" in row and "Deposit" in row
    )

    has_signed_amount = "Amount" in row

    if not has_debit_credit and not has_signed_amount:
        raise ValueError(
            "CSV must contain Withdraw/Deposit or Amount"
        )

    transaction_date = parse_date(row["Transaction Date"])
    description = row["Description"].strip()
    if not description:
        raise ValueError("Transaction description cannot be empty")


    if has_debit_credit:
        withdrawal = parse_amount(row["Withdraw"])
        deposit = parse_amount(row["Deposit"])
        amount = deposit - withdrawal
    else:
        amount = parse_amount(row["Amount"])

    return {
        "date": transaction_date,
        "description": description,
        "amount": amount
    }


def categorize_transaction(description, amount):
    """Assign a category based on transaction description."""

    text = description.lower()

    categories = {
        "Food": ["grocery", "supermarket", "restaurant"],
        "Utilities": ["electricity", "water bill", "internet"],
        "Transport": ["bus", "fuel", "taxi"],
        "Shopping": ["shopping", "clothing", "store"],
        "Healthcare": ["pharmacy", "hospital", "medical"],
        "Entertainment": ["movie", "cinema", "game"]
    }

    if amount > 0:
        return "Income"

    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "Other"


def generate_transaction_id(transaction):
    """Generate a repeatable ID for the same transaction."""

    unique_value = (
        f"{transaction['date']}|"
        f"{transaction['description'].strip().lower()}|"
        f"{transaction['amount']}"
    )

    return hashlib.sha256(
        unique_value.encode("utf-8")
    ).hexdigest()


def process_csv(file_path):
    """Read a CSV file and normalize its transactions."""

    transactions = []

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            transaction = normalize_transaction(row)

            if transaction is None:
                continue

            transaction["category"] = categorize_transaction(
                transaction["description"],
                transaction["amount"]
            )

            transaction["transaction_id"] = generate_transaction_id(
                transaction
            )

            transactions.append(transaction)

    
    return transactions

def parse_monthly_statement_text(file_path):
    """
    Parse an extracted monthly bank statement text file.

    Debit and credit are identified using the change in running balance.
    Returns statement summary and normalized transactions.
    """

    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # 1. Extract monthly summary
    if "Monthly Account Summary" not in text:
        raise ValueError("Monthly Account Summary not found")

    if "Balance check:" not in text:
        raise ValueError("Statement balance check not found")

    summary_text = text.split(
        "Monthly Account Summary", 1
    )[1].split("Balance check:", 1)[0]

    summary_amounts = re.findall(
        r"(?:NPR\s*)?([\d,]+\.\d{2})",
        summary_text
    )

    if len(summary_amounts) != 4:
        raise ValueError(
            "Could not extract all four monthly summary amounts"
        )

    opening_balance = parse_amount(summary_amounts[0])
    total_credit = parse_amount(summary_amounts[1])
    total_debit = parse_amount(summary_amounts[2])
    closing_balance = parse_amount(summary_amounts[3])

    count_matches = re.findall(
        r"(?m)^\s*(\d+)\s*$",
        summary_text
    )

    if not count_matches:
        raise ValueError("Transaction count not found")

    expected_count = int(count_matches[-1])

    # 2. Extract transaction rows
    if "Transaction Details" not in text:
        raise ValueError("Transaction Details section not found")

    transaction_lines = text.split(
        "Transaction Details", 1
    )[1].split("IMPORTANT:", 1)[0]

    lines = [
        line.strip()
        for line in transaction_lines.splitlines()
        if line.strip()
    ]

    date_pattern = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    serial_pattern = re.compile(r"^\d+$")
    amount_pattern = re.compile(
        r"^(?:NPR\s*)?[\d,]+\.\d{2}$"
    )

    # Find each row using its serial number followed by a date.
    row_starts = []

    for index in range(len(lines) - 1):
        if (
            serial_pattern.fullmatch(lines[index])
            and date_pattern.fullmatch(lines[index + 1])
        ):
            row_starts.append(index)

    if not row_starts:
        raise ValueError("No transaction rows found")

    transactions = []
    previous_balance = opening_balance

    for row_number, start in enumerate(row_starts):
        end = (
            row_starts[row_number + 1]
            if row_number + 1 < len(row_starts)
            else len(lines)
        )

        row = lines[start:end]

        serial_number = int(row[0])
        transaction_date = parse_date(row[1])

        amount_positions = [
            index
            for index, value in enumerate(row[2:], start=2)
            if amount_pattern.fullmatch(value)
        ]

        if len(amount_positions) != 2:
            raise ValueError(
                f"Transaction {serial_number}: "
                "expected one transaction amount and one balance"
            )

        first_amount_position = amount_positions[0]

        description = " ".join(
            row[2:first_amount_position]
        ).strip()

        if not description:
            raise ValueError(
                f"Transaction {serial_number}: description is empty"
            )

        transaction_amount = parse_amount(
            row[amount_positions[0]].replace("NPR", "").strip()
        )

        running_balance = parse_amount(
            row[amount_positions[1]].replace("NPR", "").strip()
        )

        balance_change = running_balance - previous_balance

        if abs(balance_change) != transaction_amount:
            raise ValueError(
                f"Transaction {serial_number}: amount does not "
                "match the change in running balance"
            )

        if balance_change < 0:
            withdrawal = transaction_amount
            deposit = Decimal("0.00")
            signed_amount = -transaction_amount
        elif balance_change > 0:
            withdrawal = Decimal("0.00")
            deposit = transaction_amount
            signed_amount = transaction_amount
        else:
            raise ValueError(
                f"Transaction {serial_number}: zero balance change"
            )

        category = categorize_transaction(
            description,
            signed_amount
        )

        transactions.append({
            "S.N": serial_number,
            "date": transaction_date,
            "description": description,
            "withdraw": withdrawal,
            "deposit": deposit,
            "balance": running_balance,
            "amount": signed_amount,
            "category": category
        })

        previous_balance = running_balance

    # 3. Validate transaction count and monthly totals
    actual_debit = sum(
        (item["withdraw"] for item in transactions),
        Decimal("0.00")
    )

    actual_credit = sum(
        (item["deposit"] for item in transactions),
        Decimal("0.00")
    )

    if len(transactions) != expected_count:
        raise ValueError(
            f"Expected {expected_count} transactions, "
            f"but extracted {len(transactions)}"
        )

    if actual_debit != total_debit:
        raise ValueError("Extracted debit total does not match statement")

    if actual_credit != total_credit:
        raise ValueError("Extracted credit total does not match statement")

    if previous_balance != closing_balance:
        raise ValueError("Final transaction balance does not match closing balance")

    if opening_balance + total_credit - total_debit != closing_balance:
        raise ValueError("Monthly balance calculation does not reconcile")

    return {
        "opening_balance": opening_balance,
        "total_credit": total_credit,
        "total_debit": total_debit,
        "closing_balance": closing_balance,
        "transaction_count": len(transactions),
        "transactions": transactions
    }


def export_statement_to_csv(statement_text_path, output_csv_path):
    """Convert an extracted monthly statement into an AWS-compatible CSV."""

    # Parse the extracted PDF text
    statement = parse_monthly_statement_text(statement_text_path)

    # Define the exact CSV columns expected by AWS Lambda
    fieldnames = [
        "S.N",
        "Transaction Date",
        "Description",
        "Withdraw",
        "Deposit",
        "Balance"
    ]

    # Write the transactions into CSV
    with open(
        output_csv_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for transaction in statement["transactions"]:
            writer.writerow({
                "S.N": transaction["S.N"],
                "Transaction Date": transaction["date"],
                "Description": transaction["description"],
                "Withdraw": transaction["withdraw"],
                "Deposit": transaction["deposit"],
                "Balance": transaction["balance"]
            })

    # Return the monthly summary
    return {
        "opening_balance": statement["opening_balance"],
        "total_credit": statement["total_credit"],
        "total_debit": statement["total_debit"],
        "closing_balance": statement["closing_balance"],
        "transaction_count": statement["transaction_count"],
        "output_file": str(output_csv_path)
    }

