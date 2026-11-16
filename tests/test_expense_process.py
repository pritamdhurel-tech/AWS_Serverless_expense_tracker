
import unittest
from decimal import Decimal
from src.expense_processor import process_csv


from src.expense_processor import (
    parse_date,
    parse_amount,
    normalize_transaction
)

from src.expense_processor import (
    categorize_transaction,
    generate_transaction_id
)

class TestExpenseProcessor(unittest.TestCase):

    def test_date_format(self):
        self.assertEqual(
            parse_date("2027-01-01"),
            "2027-01-01"
        )

    def test_alternative_date_format(self):
        self.assertEqual(
            parse_date("15/01/2027"),
            "2027-01-15"
        )

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            parse_date("2027/99/99")

    def test_amount_with_comma(self):
        self.assertEqual(
            parse_amount("6,500"),
            Decimal("6500.00")
        )

    def test_empty_amount(self):
        self.assertEqual(
            parse_amount(""),
            Decimal("0.00")
        )

    def test_deposit_and_withdrawal(self):
        row = {
            "Transaction Date": "2027-01-01",
            "Description": "Grocery Store",
            "Withdraw": "6,500",
            "Deposit": "",
            "Balance": "78,500"
        }

        result = normalize_transaction(row)

        self.assertEqual(result["amount"], Decimal("-6500"))

    def test_income_transaction(self):
        row = {
            "Transaction Date": "2027-01-01",
            "Description": "Salary",
            "Withdraw": "",
            "Deposit": "85,000",
            "Balance": "85,000"
        }

        result = normalize_transaction(row)

        self.assertEqual(result["amount"], Decimal("85000"))



    def test_missing_description_column(self):
        row = {
            "Transaction Date": "2027-01-01",
            "Withdraw": "1000",
            "Deposit": ""
        }

        with self.assertRaises(ValueError):
            normalize_transaction(row)

    def test_missing_amount_columns(self):
        row = {
            "Transaction Date": "2027-01-01",
            "Description": "Shopping"
        }

        with self.assertRaises(ValueError):
            normalize_transaction(row)


    def test_signed_amount(self):
        row = {
            "Transaction Date": "2027-01-01",
            "Description": "Online Purchase",
            "Amount": "-1200",
            "Balance": "5000"
        }

        result = normalize_transaction(row)

        self.assertEqual(result["amount"], Decimal("-1200"))


    def test_food_category(self):
        result = categorize_transaction(
            "Grocery Store", Decimal("-6500")
        )
        self.assertEqual(result, "Food")

    def test_utilities_category(self):
        result = categorize_transaction(
            "Electricity Bill", Decimal("-2200")
        )
        self.assertEqual(result, "Utilities")

    def test_transport_category(self):
        result = categorize_transaction(
            "Bus Ticket", Decimal("-800")
        )
        self.assertEqual(result, "Transport")

    def test_shopping_category(self):
        result = categorize_transaction(
            "Online Shopping", Decimal("-4500")
        )
        self.assertEqual(result, "Shopping")

    def test_healthcare_category(self):
        result = categorize_transaction(
            "Pharmacy", Decimal("-1200")
        )
        self.assertEqual(result, "Healthcare")

    def test_entertainment_category(self):
        result = categorize_transaction(
            "Movie Tickets", Decimal("-1000")
        )
        self.assertEqual(result, "Entertainment")

    def test_income_category(self):
        result = categorize_transaction(
            "Salary", Decimal("85000")
        )
        self.assertEqual(result, "Income")

    def test_unknown_category(self):
        result = categorize_transaction(
            "Unknown Payment", Decimal("-500")
        )
        self.assertEqual(result, "Other")

    def test_transaction_id_is_repeatable(self):
        transaction = {
            "date": "2027-01-02",
            "description": "Grocery Store",
            "amount": Decimal("-6500")
        }

        first_id = generate_transaction_id(transaction)
        second_id = generate_transaction_id(transaction)

        self.assertEqual(first_id, second_id)

    def test_transaction_id_changes(self):
        transaction_one = {
            "date": "2027-01-02",
            "description": "Grocery Store",
            "amount": Decimal("-6500")
        }

        transaction_two = {
            "date": "2027-01-02",
            "description": "Grocery Store",
            "amount": Decimal("-7000")
        }

        self.assertNotEqual(
            generate_transaction_id(transaction_one),
            generate_transaction_id(transaction_two)
        )


    def test_csv_financial_totals(self):
        transactions = process_csv(
            "data/converted_statement.csv"
        )

        total_income = sum(
            (t["amount"] for t in transactions if t["amount"] > 0),
            Decimal("0.00")
        )

        total_expenses = sum(
            (-t["amount"] for t in transactions if t["amount"] < 0),
            Decimal("0.00")
        )

        self.assertEqual(
            total_income,
            Decimal("64500.00")
        )

        self.assertEqual(
            total_expenses,
            Decimal("43334.00")
        )

        self.assertEqual(
            total_income - total_expenses,
            Decimal("21166.00")
        )



    def test_csv_financial_totals(self):
        transactions = process_csv(
            "data/converted_statement.csv"
        )

        total_income = sum(
            (t["amount"] for t in transactions if t["amount"] > 0),
            Decimal("0")
        )

        total_expenses = sum(
            (-t["amount"] for t in transactions if t["amount"] < 0),
            Decimal("0")
        )

        net_cash_flow = total_income - total_expenses

        print("\n--- EXPENSE TRACKER REPORT ---")
        print(f"Total Income: {total_income}")
        print(f"Total Expenses: {total_expenses}")
        print(f"Net Cash Flow: {net_cash_flow}")
        print(f"Transaction Count: {len(transactions)}")
        print("------------------------------")

        self.assertEqual(total_income, Decimal("64500.00"))
        self.assertEqual(total_expenses, Decimal("43334.00"))
        self.assertEqual(total_income - total_expenses, Decimal("21166.00")
)


    def test_empty_description(self):
        row = {
            "Transaction Date": "2027-01-01",
            "Description": "",
            "Withdraw": "1000",
            "Deposit": ""
        }

        with self.assertRaises(ValueError):
            normalize_transaction(row)


    def test_empty_row(self):
        row = {
            "Transaction Date": "",
            "Description": "",
            "Withdraw": "",
            "Deposit": "",
            "Balance": ""
        }

        self.assertIsNone(normalize_transaction(row))



if __name__ == "__main__":
    unittest.main()
