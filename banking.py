import sys
sys.stdout.reconfigure(line_buffering=True)

import gspread
from google.oauth2.service_account import Credentials
import random
from prettytable import PrettyTable
from datetime import datetime
import re
import os
import json

# ==============================================
# 🔧 GOOGLE SHEETS SETUP
# ==============================================

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

CREDS = Credentials.from_service_account_file("creds.json")
SCOPED_CREDS = CREDS.with_scopes(SCOPE)
CLIENT = gspread.authorize(SCOPED_CREDS)
SHEET = CLIENT.open("banking_app")


def get_or_create_worksheet(title, headers):
    try:
        sheet = SHEET.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        sheet = SHEET.add_worksheet(title=title, rows="1000", cols=str(len(headers)))
        sheet.append_row(headers)
    return sheet


accounts_sheet = get_or_create_worksheet(
    "accounts", ["Name", "Account Number", "Balance"]
)
transactions_sheet = get_or_create_worksheet(
    "transactions",
    ["Account Number", "Type", "Amount", "Balance After", "Date & Time"]
)

# ==============================================
# 🧹 UTILITIES
# ==============================================

def normalize_headers(record):
    return {k.lower().strip().replace(" ", "_"): v for k, v in record.items()}


def clean_account_numbers():
    print("🔧 Cleaning account numbers...", flush=True)
    records = [normalize_headers(r) for r in accounts_sheet.get_all_records()]
    used_numbers = set()

    for i, record in enumerate(records, start=2):
        raw = str(record.get("account_number", ""))
        cleaned = re.sub(r"\D", "", raw).zfill(10)[:10]

        while cleaned in used_numbers or cleaned == "":
            cleaned = str(random.randint(1000000000, 9999999999))

        used_numbers.add(cleaned)

        if cleaned != raw:
            accounts_sheet.update_cell(i, 2, cleaned)
            print(f"✅ Fixed {raw} → {cleaned}", flush=True)

    print("🎉 Account numbers cleaned.\n", flush=True)


def log_transaction(account, t_type, amount, balance):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions_sheet.append_row([
        account,
        t_type,
        f"{amount:.2f}",
        f"{balance:.2f}",
        timestamp
    ])


def safe_float(value):
    try:
        amount = float(str(value).replace("£", "").replace(",", "").strip())
        if amount < 0:
            raise ValueError
        return amount
    except ValueError:
        raise ValueError("Invalid amount.")


# ==============================================
# 💼 ACCOUNT OPERATIONS
# ==============================================

def find_account(account_number):
    sheet = SHEET.worksheet("accounts")
    values = sheet.get_all_values()
    headers = [h.lower().replace("£", "").strip() for h in values[0]]

    acc_i = headers.index("account number")
    bal_i = next(i for i, h in enumerate(headers) if h.startswith("balance"))

    for row_i, row in enumerate(values[1:], start=2):
        if row[acc_i] == str(account_number):
            return row_i, float(row[bal_i])

    return None, None


def generate_account_number():
    while True:
        num = random.randint(1000000000, 9999999999)
        _, acc = find_account(num)
        if acc is None:
            return num


def create_account(name, balance):
    acc_num = generate_account_number()
    accounts_sheet.append_row([name, acc_num, balance])
    log_transaction(acc_num, "Account Created", balance, balance)

    print("✅ Account created", flush=True)
    print(f"Name: {name}", flush=True)
    print(f"Account Number: {acc_num}", flush=True)
    print(f"Balance: £{balance:.2f}\n", flush=True)


def deposit(account, amount):
    row, balance = find_account(account)
    if row is None:
        print("❌ Account not found.", flush=True)
        return

    new_balance = balance + amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account, "Deposit", amount, new_balance)

    print(f"✅ Deposited £{amount:.2f}", flush=True)
    print(f"New balance: £{new_balance:.2f}\n", flush=True)


def withdraw(account, amount):
    row, balance = find_account(account)
    if row is None:
        print("❌ Account not found.", flush=True)
        return

    if amount > balance:
        print("❌ Insufficient funds.", flush=True)
        return

    new_balance = balance - amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account, "Withdrawal", amount, new_balance)

    print(f"✅ Withdrawn £{amount:.2f}", flush=True)
    print(f"New balance: £{new_balance:.2f}\n", flush=True)


def display_balance(account):
    _, balance = find_account(account)
    if balance is None:
        print("❌ Account not found.", flush=True)
    else:
        print(f"💰 Balance: £{balance:.2f}\n", flush=True)


# ==============================================
# 📊 DISPLAY
# ==============================================

def view_transaction_history(account):
    sheet = SHEET.worksheet("transactions")
    rows = sheet.get_all_values()[1:]

    table = PrettyTable(["Date", "Type", "Amount", "Balance"])
    for r in rows:
        if r[0] == str(account):
            table.add_row([r[4], r[1], f"£{r[2]}", f"£{r[3]}"])

    print(table if table.rows else "No transactions.\n", flush=True)


def print_database():
    sheet = SHEET.worksheet("accounts")
    rows = sheet.get_all_values()[1:]

    table = PrettyTable(["Name", "Account", "Balance"])
    for r in rows:
        table.add_row([r[0], r[1], f"£{float(r[2]):.2f}"])

    print(table, flush=True)


# ==============================================
# 🖥️ TERMINAL
# ==============================================

def clear_screen():
    print("\n" * 2, flush=True)


def get_choice():
    raw = input("Enter option (1–7): ").strip()
    print(f">>> {raw}", flush=True)
    return raw if raw in list("1234567") else None


def main():
    clear_screen()
    print("🏦 Banking App", flush=True)
    print("=" * 30, flush=True)

    clean_account_numbers()

    while True:
        print("\n1 Create Account", flush=True)
        print("2 Withdraw", flush=True)
        print("3 Deposit", flush=True)
        print("4 Balance", flush=True)
        print("5 History", flush=True)
        print("6 Admin View", flush=True)
        print("7 Exit", flush=True)

        choice = get_choice()
        if not choice:
            print("❌ Invalid choice.", flush=True)
            continue

        try:
            if choice == "1":
                create_account(
                    input("Name: "),
                    safe_float(input("Initial balance: "))
                )

            elif choice == "2":
                withdraw(input("Account: "), safe_float(input("Amount: ")))

            elif choice == "3":
                deposit(input("Account: "), safe_float(input("Amount: ")))

            elif choice == "4":
                display_balance(input("Account: "))

            elif choice == "5":
                view_transaction_history(input("Account: "))

            elif choice == "6":
                if input("Admin password: ") == "admin123":
                    print_database()
                else:
                    print("❌ Access denied.", flush=True)

            elif choice == "7":
                print("👋 Goodbye!", flush=True)
                break

        except Exception as e:
            print(f"💥 Error: {e}", flush=True)


if __name__ == "__main__":
    main()
