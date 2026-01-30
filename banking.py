import sys
import os
import time
import re
import random
import warnings
import getpass
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from prettytable import PrettyTable

# ======================================================
#   ADMIN PASSWORD (ENV VAR)
# ======================================================

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    print("ADMIN_PASSWORD environment variable not set.")

# ======================================================
#   STDOUT CONFIG
# ======================================================

sys.stdout.reconfigure(line_buffering=True)

# ======================================================
#   GOOGLE SHEETS SETUP
# ======================================================

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]


def load_credentials():
    for _ in range(10):
        if os.path.exists("creds.json"):
            break
        time.sleep(0.3)

    if not os.path.exists("creds.json"):
        print("creds.json not found.")
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


# ======================================================
#  UTILITIES
# ======================================================

def read_input():
    return sys.stdin.readline().strip()


def prompt(text):
    print(text)
    print("> ", end="")
    return read_input()


def prompt_password(text):
    print(text)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pwd = getpass.getpass("")
    except Exception:
        pwd = read_input()

    print("****")
    return pwd


def validate_account_number(account):
    return bool(re.fullmatch(r"\d{10}", str(account)))


def format_account_number(account):
    s = str(account)
    if len(s) == 10 and s.isdigit():
        return f"{s[:4]}-{s[4:7]}-{s[7:]}"
    return s


def safe_float(value):
    try:
        amount = float(str(value).replace("£", "").replace(",", "").strip())
        if amount < 0:
            raise ValueError
        return amount
    except ValueError:
        raise ValueError("Invalid amount entered.")


def clean_account_numbers():
    records = accounts_sheet.get_all_records()
    used = set()

    for i, record in enumerate(records, start=2):
        raw = str(record.get("Account Number", ""))
        cleaned = re.sub(r"\D", "", raw).zfill(10)[:10]

        while cleaned in used:
            cleaned = str(random.randint(1000000000, 9999999999))

        used.add(cleaned)

        if cleaned != raw:
            accounts_sheet.update_cell(i, 2, cleaned)


def log_transaction(account, t_type, amount, balance):
    transactions_sheet.append_row([
        account,
        t_type,
        f"{amount:.2f}",
        f"{balance:.2f}",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ])


# ======================================================
#  ACCOUNT OPERATIONS
# ======================================================

def find_account(account_number):
    values = accounts_sheet.get_all_values()
    headers = [h.lower().strip() for h in values[0]]

    acc_i = headers.index("account number")
    bal_i = headers.index("balance")

    for row_i, row in enumerate(values[1:], start=2):
        if row[acc_i] == str(account_number):
            try:
                return row_i, float(str(row[bal_i]).replace(",", ""))
            except ValueError:
                return row_i, 0.0

    return None, None


def generate_account_number():
    while True:
        num = random.randint(1000000000, 9999999999)
        _, bal = find_account(num)
        if bal is None:
            return num


def create_account(name, balance):
    acc = generate_account_number()
    accounts_sheet.append_row([name, acc, balance])
    log_transaction(acc, "Account Created", balance, balance)

    print("Account created")
    print(f"Name: {name}")
    print(f"Account Number: {format_account_number(acc)}")
    print(f"Balance: £{balance:.2f}\n")


def deposit(account, amount):
    row, balance = find_account(account)
    if row is None:
        print("Account not found.\n")
        return

    new_balance = balance + amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account, "Deposit", amount, new_balance)

    print(f"Deposited £{amount:.2f}")
    print(f"New balance: £{new_balance:.2f}\n")


def withdraw(account, amount):
    row, balance = find_account(account)
    if row is None:
        print("Account not found.\n")
        return

    if amount > balance:
        print("Insufficient funds.\n")
        return

    new_balance = balance - amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account, "Withdrawal", amount, new_balance)

    print(f"Withdrawn £{amount:.2f}")
    print(f"New balance: £{new_balance:.2f}\n")


def display_balance(account):
    _, balance = find_account(account)
    if balance is None:
        print("Account not found.\n")
    else:
        print(f"Balance for {format_account_number(account)}: £{balance:.2f}\n")


# ======================================================
# DISPLAY
# ======================================================

def view_transaction_history(account):
    rows = transactions_sheet.get_all_values()[1:]
    print(f"Transactions for {format_account_number(account)}\n")

    table = PrettyTable(["Date", "Type", "Amount", "Balance"])
    for r in rows:
        if r[0] == str(account):
            table.add_row([r[4], r[1], f"£{r[2]}", f"£{r[3]}"])

    print(table if table.rows else "No transactions.\n")


def print_database():
    rows = accounts_sheet.get_all_values()[1:]
    table = PrettyTable(["Name", "Account", "Balance"])

    for r in rows:
        bal = float(str(r[2]).replace(",", ""))
        table.add_row([r[0], format_account_number(r[1]), f"£{bal:.2f}"])

    print(table)


# ======================================================
#  MAIN LOOP
# ======================================================

def show_menu():
    print("\n==============================")
    print("🏦 Welcome to the Banking App")
    print("==============================")
    print("SELECT AN OPTION")
    print("1. Create Account")
    print("2. Withdraw Funds")
    print("3. Deposit Funds")
    print("4. Display Balance")
    print("5. View Transaction History")
    print("6. Print Database (Admin)")
    print("7. Exit")
    print("==============================")
    print("> ", end="")


def main():
    clean_account_numbers()

    while True:
        show_menu()
        choice = read_input()

        try:
            if choice == "1":
                name = prompt("Enter account name")
                balance = safe_float(prompt("Enter initial balance (£)"))
                create_account(name, balance)

            elif choice == "2":
                acc = prompt("Enter account number")
                if not validate_account_number(acc):
                    print("Account number incorrect.\n")
                    continue
                amt = safe_float(prompt("Enter withdrawal amount (£)"))
                withdraw(acc, amt)

            elif choice == "3":
                acc = prompt("Enter account number")
                if not validate_account_number(acc):
                    print("Account number incorrect.\n")
                    continue
                amt = safe_float(prompt("Enter deposit amount (£)"))
                deposit(acc, amt)

            elif choice == "4":
                acc = prompt("Enter account number")
                if not validate_account_number(acc):
                    print("Account number incorrect.\n")
                    continue
                display_balance(acc)

            elif choice == "5":
                acc = prompt("Enter account number")
                if not validate_account_number(acc):
                    print("Account number incorrect.\n")
                    continue
                view_transaction_history(acc)

            elif choice == "6":
                password = prompt_password("Enter admin password")
                if password == ADMIN_PASSWORD:
                    print_database()
                else:
                    print("Access denied.\n")

            elif choice == "7":
                print("Goodbye!")
                break

            else:
                print("Invalid choice.\n")

        except ValueError as e:
            print(f"{e}\n")


if __name__ == "__main__":
    main()
