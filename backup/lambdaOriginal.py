
import boto3
import csv
import json
import os
import urllib.parse

from decimal import Decimal, InvalidOperation
from collections import defaultdict
from datetime import datetime, timezone
from io import StringIO

sns = boto3.client("sns")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

transactions_table = dynamodb.Table(
    os.environ["TRANSACTIONS_TABLE"]
)

summary_table = dynamodb.Table(
    os.environ["SUMMARY_TABLE"]
)


BUCKET_NAME = os.environ.get("BUCKET_NAME")


# Convert CSV amounts into Decimal safely
def get_amount(value):
    if not value or not value.strip():
        return Decimal("0")

    try:
        amount = Decimal(value.replace(",", "").strip())

        if amount < 0:
            raise ValueError("Negative amounts are not supported")

        return amount

    except InvalidOperation:
        raise ValueError(f"Invalid amount: {value}")


# Categorize transactions using simple rules
def categorize(description):
    text = description.lower()

    categories = {
        "Food": [
            "restaurant", "food", "cafe",
            "hotel", "grocery", "mart"
        ],
        "Utilities": [
            "electricity", "internet", "water",
            "telephone", "nepal telecom"
        ],
        "Shopping": [
            "shopping", "store", "clothing",
            "purchase"
        ],
        "Transport": [
            "petrol", "fuel", "taxi",
            "bus", "transport"
        ],
        "Healthcare": [
            "hospital", "medical", "pharmacy",
            "doctor"
        ],
        "Entertainment": [
            "movie", "cinema", "game",
            "entertainment"
        ]
    }

    for category, keywords in categories.items():
        if any(word in text for word in keywords):
            return category

    return "Other"


def lambda_handler(event, context):

    try:
        for record in event["Records"]:

            bucket = record["s3"]["bucket"]["name"]

            key = urllib.parse.unquote_plus(
                record["s3"]["object"]["key"]
            )

            # Only process CSV files in incoming/
            if not key.startswith("incoming/") or not key.lower().endswith(".csv"):
                print(f"Skipping object: {key}")
                continue

            print(f"Processing file: {key}")

            # Download CSV from S3
            response = s3.get_object(
                Bucket=bucket,
                Key=key
            )

            csv_content = response["Body"].read().decode("utf-8-sig")

            reader = csv.DictReader(StringIO(csv_content))

            required_columns = [
                "S.N",
                "Transaction Date",
                "Description",
                "Withdraw",
                "Deposit",
                "Balance"
            ]

            if reader.fieldnames != required_columns:
                raise ValueError(
                    f"Invalid CSV headers. Expected: {required_columns}"
                )

            transactions = []
            category_totals = defaultdict(
                lambda: Decimal("0")
            )

            total_income = Decimal("0")
            total_expenses = Decimal("0")
            closing_balance = None

            for row in reader:

                description = row["Description"].strip()

                withdraw = get_amount(row["Withdraw"])
                deposit = get_amount(row["Deposit"])
                balance = get_amount(row["Balance"])

                if withdraw > 0 and deposit > 0:
                    raise ValueError(
                        "A transaction cannot have both withdrawal and deposit"
                    )

                if withdraw == 0 and deposit == 0:
                    raise ValueError(
                        "Transaction must have a withdrawal or deposit"
                    )

                category = (
                    categorize(description)
                    if withdraw > 0
                    else "Income"
                )

                total_expenses += withdraw
                total_income += deposit

                if withdraw > 0:
                    category_totals[category] += withdraw

                closing_balance = balance

                transactions.append({
                    "transaction_id": row["S.N"],
                    "date": row["Transaction Date"],
                    "description": description,
                    "withdraw": withdraw,
                    "deposit": deposit,
                    "balance": balance,
                    "category": category
                })

            if not transactions:
                raise ValueError("CSV contains no transactions")

            net_cash_flow = total_income - total_expenses

            # Generate automated remarks
            remarks = []

            remarks.append(
                f"You received {total_income} in total deposits."
            )

            remarks.append(
                f"You spent {total_expenses} in total withdrawals."
            )

            if category_totals:
                highest_category = max(
                    category_totals,
                    key=category_totals.get
                )

                remarks.append(
                    f"Your highest expense category is "
                    f"{highest_category}, with "
                    f"{category_totals[highest_category]} spent."
                )

            if net_cash_flow > 0:
                remarks.append(
                    "Your deposits exceeded your withdrawals."
                )
            elif net_cash_flow < 0:
                remarks.append(
                    "Your withdrawals exceeded your deposits."
                )
            else:
                remarks.append(
                    "Your deposits and withdrawals were equal."
                )

            # Prepare report
            report = {
                "source_file": key,
                "processed_at": datetime.now(
                    timezone.utc
                ).isoformat(),

                "summary": {
                    "transaction_count": len(transactions),
                    "total_income": total_income,
                    "total_expenses": total_expenses,
                    "net_cash_flow": net_cash_flow,
                    "closing_balance": closing_balance
                },

                "category_breakdown": dict(
                    category_totals
                ),

                "remarks": remarks,
                "transactions": transactions
            }

            # Unique identifier for this uploaded statement
            statement_id = f"{bucket}/{key}"

            # Store individual transactions
            with transactions_table.batch_writer() as batch:

                for transaction in transactions:

                    batch.put_item(
                        Item={
                            "statement_id": statement_id,
                            "transaction_id": str(
                                transaction["transaction_id"]
                            ),
                            "date": transaction["date"],
                            "description": transaction["description"],
                            "withdraw": transaction["withdraw"],
                            "deposit": transaction["deposit"],
                            "balance": transaction["balance"],
                            "category": transaction["category"]
                        }
                    )


            # Store monthly expense summary
            summary_table.put_item(
                Item={
                    "statement_id": statement_id,
                    "source_file": key,
                    "processed_at": report["processed_at"],
                    "transaction_count": len(transactions),
                    "total_income": total_income,
                    "total_expenses": total_expenses,
                    "net_cash_flow": net_cash_flow,
                    "closing_balance": closing_balance,
                    "category_breakdown": dict(category_totals),
                    "remarks": remarks
                }
            )

            print("Transactions saved to DynamoDB")
            print("Expense summary saved to DynamoDB")

            # Save report to S3 processed folder
            filename = os.path.basename(key)
            report_key = (
                "processed/"
                + filename.rsplit(".", 1)[0]
                + "-report.json"
            )

            s3.put_object(
                Bucket=bucket,
                Key=report_key,
                Body=json.dumps(
                    report,
                    indent=4,
                    default=str
                ).encode("utf-8"),
                ContentType="application/json"
            )

            print("Expense report created:", report_key)

            print(
                "Total income:", total_income,
                "Total expenses:", total_expenses,
                "Net cash flow:", net_cash_flow
            )

            # SNS notification
            sns.publish(
                TopicArn=os.environ["SNS_TOPIC_ARN"],
                Subject="Your Expense Tracker Report",
                Message=f"""
Expense Tracker Report

Total Income: {total_income}
Total Expenses: {total_expenses}
Net Cash Flow: {net_cash_flow}
Closing Balance: {closing_balance}
Transaction Count: {len(transactions)}

Remarks:
{chr(10).join(remarks)}
"""
            )

            print("SNS email notification sent successfully")

        return {
            "statusCode": 200,
            "body": json.dumps(
                "Expense processing completed successfully"
            )
        }

    except Exception as error:
        print("Expense processing failed:", str(error))
        raise
