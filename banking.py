import sys
import os
import re
import random
import warnings
import getpass
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from prettytable import PrettyTable

# ======================================================
#   CONFIG
# ======================================================

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    print("Admin features (Print Database) will be disabled unless ADMIN_PASSWORD env var is set.\n")

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Transfer settings
MIN_TRANSFER_AMOUNT = 10.00
TRANSFER_FEE_PERCENT = 0.01   # 1%
MIN_FEE = 1.00

# ======================================================
#   GOOGLE SHEETS SETUP
# ======================================================

def load_credentials():
    for _ in range(10):
        if os.path.exists("creds.json"):
            break
        time.sleep(0.3)

    if not os.path.exists("creds.json"):
        print("Error: creds.json not found.")
        sys.exit(1)

    return Credentials.from_service_account_file("creds.json", scopes=SCOPE)


CREDS = load_credentials()
CLIENT = gspread.authorize(CREDS)
SHEET = CLIENT.open("banking_app")


def get_or_create_worksheet(title, headers):
    try:
        sheet = SHEET.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        sheet = SHEET.add_worksheet(title=title, rows=1000, cols=len(headers))
        sheet.append_row(headers)
    return sheet


accounts_sheet = get_or_create_worksheet(
    "accounts", ["Name", "Account Number", "Balance", "Last Updated"]
)

transactions_sheet = get_or_create_worksheet(
    "transactions",
    ["Account Number", "Type", "Amount", "Balance After", "Date & Time"]
)


# ======================================================
#   UTILITIES
# ======================================================

def read_input(prompt_text=""):
    if prompt_text:
        print(prompt_text)
        print("> ", end="", flush=True)
    return sys.stdin.readline().strip()


def prompt_password(prompt_text):
    print(prompt_text)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pwd = getpass.getpass("")
    except Exception:
        pwd = read_input()
    print("****")
    return pwd


def validate_account_number(acc):
    return bool(re.fullmatch(r"\d{10}", str(acc)))


def format_account_number(acc):
    s = str(acc)
    if len(s) == 10 and s.isdigit():
        return f"{s[:4]}-{s[4:7]}-{s[7:]}"
    return s


def parse_amount(value):
    try:
        cleaned = str(value).replace("£", "").replace(",", "").strip()
        amount = float(cleaned)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        return amount
    except (ValueError, TypeError):
        raise ValueError("Invalid amount. Please enter a positive number.")


def parse_balance(value):
    if not value:
        return 0.0
    try:
        cleaned = re.sub(r'[^\d.]', '', str(value).strip())
        return float(cleaned)
    except (ValueError, TypeError):
        print(f"Warning: Invalid balance value '{value}' → treated as 0.0")
        return 0.0


def get_current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_transaction(account, t_type, amount, balance_after):
    transactions_sheet.append_row([
        account,
        t_type,
        f"{amount:.2f}",
        f"{balance_after:.2f}",
        get_current_timestamp()
    ])


def get_valid_account_number(prompt="Enter 10-digit account number"):
    while True:
        acc = read_input(prompt + "\n(or type 'q' / 'quit' / 'exit' to cancel)")
        acc_clean = acc.strip().lower()

        if acc_clean in ("q", "quit", "exit"):
            print("Operation cancelled.\n")
            return None

        if validate_account_number(acc):
            return acc

        print("Invalid account number, please try again or press 'q' to cancel/quit!\n")


# ======================================================
#   ACCOUNT OPERATIONS
# ======================================================

def find_account(account_number):
    values = accounts_sheet.get_all_values()
    if len(values) < 2:
        return None, None, None, None

    headers = [str(h).lower().strip() for h in values[0]]

    name_idx = None
    acc_idx = None
    bal_idx = None
    upd_idx = None

    for i, h in enumerate(headers):
        if "name" in h:
            name_idx = i
        if any(k in h for k in ["account", "code", "acc"]):
            acc_idx = acc_idx or i
        if "balance" in h or "bal" in h:
            bal_idx = bal_idx or i
        if any(k in h for k in ["updated", "timestamp", "time", "last", "update", "stamps"]):
            upd_idx = upd_idx or i

    if acc_idx is None or bal_idx is None:
        print("Error: Cannot find required columns.")
        return None, None, None, None

    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) > acc_idx and str(row[acc_idx]).strip() == str(account_number):
            name = row[name_idx] if name_idx is not None and len(row) > name_idx else "Unknown"
            balance = parse_balance(row[bal_idx] if len(row) > bal_idx else "")
            last_upd = row[upd_idx] if upd_idx is not None and len(row) > upd_idx else "—"
            return row_idx, name, balance, last_upd
    return None, None, None, None


def update_balance(row, new_balance):
    now = get_current_timestamp()
    accounts_sheet.batch_update([{
        'range': f'C{row}:D{row}',
        'values': [[f"{new_balance:.2f}", now]]
    }])


def transfer_money():
    print("\n" + "-"*50)
    print("           MONEY TRANSFER")
    print("-"*50)

    from_acc = get_valid_account_number("Source account number")
    if from_acc is None:
        return

    to_acc = get_valid_account_number("Destination account number")
    if to_acc is None:
        return

    if from_acc == to_acc:
        print("Cannot transfer money to the same account.\n")
        return

    try:
        amount_str = read_input("Amount to transfer (£)")
        amount = parse_amount(amount_str)
    except ValueError as e:
        print(f"Error: {e}\n")
        return

    if amount < MIN_TRANSFER_AMOUNT:
        print(f"Minimum transfer amount is £{MIN_TRANSFER_AMOUNT:.2f}.\n")
        return

    from_row, from_name, from_balance, _ = find_account(from_acc)
    to_row, to_name, to_balance, _ = find_account(to_acc)

    if from_row is None or to_row is None:
        print("One or both accounts not found.\n")
        return

    fee = max(MIN_FEE, amount * TRANSFER_FEE_PERCENT)
    total_debit = amount + fee

    if total_debit > from_balance:
        print(f"Insufficient funds. Available: £{from_balance:.2f}")
        print(f"Required (amount + fee): £{total_debit:.2f}\n")
        return

    # Confirmation
    print("\n" + "-"*50)
    print("TRANSFER SUMMARY")
    print("-"*50)
    print(f"From     : {from_name} ({format_account_number(from_acc)})")
    print(f"To       : {to_name} ({format_account_number(to_acc)})")
    print(f"Amount   : £{amount:.2f}")
    print(f"Fee (1%, min £{MIN_FEE:.2f}) : £{fee:.2f}")
    print(f"Total debit from source : £{total_debit:.2f}")
    print(f"Source balance after: £{from_balance - total_debit:.2f}")
    print(f"Destination balance after: £{to_balance + amount:.2f}")
    print("-"*50)

    confirm = read_input("Confirm transfer? (y/n)").strip().lower()
    if confirm not in ('y', 'yes'):
        print("Transfer cancelled.\n")
        return

    # Execute transfer
    new_from = from_balance - total_debit
    new_to = to_balance + amount

    update_balance(from_row, new_from)
    update_balance(to_row, new_to)

    log_transaction(from_acc, f"Transfer Out to {format_account_number(to_acc)} (fee £{fee:.2f})", -total_debit, new_from)
    log_transaction(to_acc, f"Transfer In from {format_account_number(from_acc)}", amount, new_to)

    print("\n" + "="*50)
    print("TRANSFER COMPLETED SUCCESSFULLY")
    print("="*50)
    print(f"Amount transferred: £{amount:.2f}")
    print(f"Fee charged      : £{fee:.2f}")
    print(f"Source account   : {format_account_number(from_acc)} → £{new_from:.2f}")
    print(f"Destination account: {format_account_number(to_acc)} → £{new_to:.2f}")
    print("="*50 + "\n")


def generate_account_number(max_attempts=1000):
    used = {str(r[1]).strip() for r in accounts_sheet.get_all_values()[1:] if len(r) > 1}
    for _ in range(max_attempts):
        num = str(random.randint(1000000000, 9999999999))
        if num not in used:
            return num
    raise RuntimeError("Could not generate a unique account number after many attempts.")


def create_account(name, initial_balance):
    acc = generate_account_number()
    now = get_current_timestamp()
    accounts_sheet.append_row([
        name,
        acc,
        f"{initial_balance:.2f}",
        now
    ])
    log_transaction(acc, "Account Created", initial_balance, initial_balance)

    print("\nAccount created successfully!")
    print(f"Name           : {name}")
    print(f"Account Number : {format_account_number(acc)}")
    print(f"Initial Balance: £{initial_balance:.2f}")
    print(f"Created        : {now}\n")


def deposit(account, amount):
    row, balance, _ = find_account(account)
    if row is None:
        print("Account not found.\n")
        return

    new_balance = balance + amount
    now = get_current_timestamp()

    accounts_sheet.batch_update([{
        'range': f'C{row}:D{row}',
        'values': [[f"{new_balance:.2f}", now]]
    }])

    log_transaction(account, "Deposit", amount, new_balance)

    print(f"Deposited £{amount:.2f}")
    print(f"New balance   : £{new_balance:.2f}")
    print(f"Updated       : {now}\n")


def withdraw(account, amount):
    row, balance, _ = find_account(account)
    if row is None:
        print("Account not found.\n")
        return

    if amount > balance:
        print("Insufficient funds.\n")
        return

    new_balance = balance - amount
    now = get_current_timestamp()

    accounts_sheet.batch_update([{
        'range': f'C{row}:D{row}',
        'values': [[f"{new_balance:.2f}", now]]
    }])

    log_transaction(account, "Withdrawal", amount, new_balance)

    print(f"Withdrawn £{amount:.2f}")
    print(f"New balance   : £{new_balance:.2f}")
    print(f"Updated       : {now}\n")


def display_balance(account):
    _, balance, last_upd = find_account(account)
    if balance is None:
        print("Account not found.\n")
    else:
        print(f"Balance for {format_account_number(account)}: £{balance:.2f}")
        print(f"Last updated  : {last_upd}")
        print()


def view_transaction_history(account):
    rows = transactions_sheet.get_all_values()[1:]
    matching = [r for r in rows if len(r) > 0 and str(r[0]).strip() == str(account)]

    print(f"\nTransaction history for {format_account_number(account)}\n")

    if not matching:
        print("No transactions found.\n")
        return

    table = PrettyTable(["Date & Time", "Type", "Amount", "Balance After"])
    for r in matching:
        if len(r) >= 5:
            table.add_row([r[4], r[1], f"£{r[2]}", f"£{r[3]}"])

    print(table)
    print()


def print_all_accounts():
    rows = accounts_sheet.get_all_values()[1:]
    if not rows:
        print("No accounts found.\n")
        return

    table = PrettyTable(["Name", "Account Number", "Balance", "Last Updated"])
    for r in rows:
        if len(r) < 3:
            continue
        bal = parse_balance(r[2])
        last_upd = r[3] if len(r) > 3 else "—"
        table.add_row([
            r[0],
            format_account_number(r[1]),
            f"£{bal:.2f}",
            last_upd
        ])

    print("\nAll Accounts:")
    print(table)
    print()


# ======================================================
#   MAIN INTERFACE
# ======================================================

def show_menu():
    print("\n" + "="*40)
    print("      🏦  DREAMS BANKING TERMINAL  ")
    print("="*40)
    print("1. Create New Account")
    print("2. Deposit Funds")
    print("3. Withdraw Funds")
    print("4. Check Balance")
    print("5. View Transaction History")
    print("6. Transfer Money")
    print("7. Print Database (Admin)")
    print("8. Exit")
    print("="*40)
    print("> ", end="", flush=True)


def main():
    while True:
        show_menu()
        choice = sys.stdin.readline().strip().lower()

        if choice in ("q", "quit", "exit"):
            print("\nThank you for using the Dreams Banking Terminal. Goodbye!\n")
            break

        try:
            if choice == "1":
                name = read_input("Enter account holder's name")
                if not name.strip():
                    print("Name cannot be empty.\n")
                    continue
                amt_str = read_input("Enter initial balance (£)")
                balance = parse_amount(amt_str)
                create_account(name, balance)

            elif choice in ("2", "3", "4", "5"):
                acc = get_valid_account_number()
                if acc is None:
                    continue

                if choice == "2":
                    amt = parse_amount(read_input("Enter deposit amount (£)"))
                    deposit(acc, amt)
                elif choice == "3":
                    amt = parse_amount(read_input("Enter withdrawal amount (£)"))
                    withdraw(acc, amt)
                elif choice == "4":
                    display_balance(acc)
                elif choice == "5":
                    view_transaction_history(acc)

            elif choice == "6":
                transfer_money()

            elif choice == "7":
                if not ADMIN_PASSWORD:
                    print("Admin features are disabled (ADMIN_PASSWORD environment variable is not set).\n")
                else:
                    pwd = prompt_password("Enter admin password:")
                    if pwd == ADMIN_PASSWORD:
                        print_all_accounts()
                    else:
                        print("Access denied.\n")

            elif choice == "8":
                print("\nThank you for using the Dreams Banking Terminal. Goodbye!\n")
                break

            else:
                print("Invalid choice, please try again or press 'q' to quit!\n")

        except ValueError as e:
            print(f"Error: {e}\n")
        except Exception as e:
            print(f"Unexpected error: {e}\n")


if __name__ == "__main__":
    main()