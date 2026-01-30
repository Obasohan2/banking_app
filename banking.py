import gspread
from google.oauth2.service_account import Credentials
import random
from prettytable import PrettyTable
from datetime import datetime
import re
import os
import json
import sys
import time

# ==============================================
# 🔧 GOOGLE SHEETS SETUP (HEROKU SAFE)
# ==============================================

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]


def load_credentials():
    """Wait for creds.json to exist and load it safely."""
    for _ in range(10):
        if os.path.exists("creds.json"):
            break
        time.sleep(0.3)

    if not os.path.exists("creds.json"):
        print("❌ creds.json not found. Check Heroku config vars.")
        sys.exit(1)

    return Credentials.from_service_account_file("creds.json", scopes=SCOPE)

CREDS = load_credentials()
CLIENT = gspread.authorize(CREDS)
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


def prompt(text):
    print(text, flush=True)
    return input("> ").strip()


def get_choice():
    choice = prompt("Enter your choice (1–7)")
    if choice not in [str(i) for i in range(1, 8)]:
        print("❌ Invalid choice. Enter a number 1–7.", flush=True)
        return None
    return choice


def show_menu():
    print("\n" + "=" * 30, flush=True)
    print("🏦 Welcome to the Banking App", flush=True)
    print("=" * 30, flush=True)
    print("1. Create Account", flush=True)
    print("2. Withdraw Funds", flush=True)
    print("3. Deposit Funds", flush=True)
    print("4. Display Balance", flush=True)
    print("5. View Transaction History", flush=True)
    print("6. Print Database (Admin)", flush=True)
    print("7. Exit", flush=True)
    print("=" * 30, flush=True)


def main():
    print("Running your file: banking.py\n", flush=True)

    try:
        clean_account_numbers()

        while True:
            show_menu()
            choice = get_choice()

            if not choice:
                continue

            if choice == "1":
                name = prompt("Enter account name")
                balance = safe_float(prompt("Enter initial balance (£)"))
                create_account(name, balance)

            elif choice == "2":
                acc = prompt("Enter account number")
                amt = safe_float(prompt("Enter withdrawal amount (£)"))
                withdraw(acc, amt)

            elif choice == "3":
                acc = prompt("Enter account number")
                amt = safe_float(prompt("Enter deposit amount (£)"))
                deposit(acc, amt)

            elif choice == "4":
                acc = prompt("Enter account number")
                display_balance(acc)

            elif choice == "5":
                acc = prompt("Enter account number")
                view_transaction_history(acc)

            elif choice == "6":
                pw = prompt("Enter admin password")
                if pw != "admin123":
                    print("❌ Access denied.", flush=True)
                else:
                    print_database()

            elif choice == "7":
                print("👋 Goodbye!", flush=True)
                break

    except Exception as e:
        print(f"💥 Fatal error: {e}", flush=True)


if __name__ == "__main__":
    main()
