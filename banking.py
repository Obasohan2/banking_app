import gspread
from google.oauth2.service_account import Credentials
import random
from prettytable import PrettyTable
from datetime import datetime
import re
import os

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
    """Ensure a worksheet exists; create if missing."""
    try:
        sheet = SHEET.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        sheet = SHEET.add_worksheet(
            title=title, rows="1000", cols=str(len(headers))
            )
        sheet.append_row(headers)
    return sheet


accounts_sheet = get_or_create_worksheet(
    "accounts", ["Name", "Account Number", "Balance"]
    )
transactions_sheet = get_or_create_worksheet(
    "transactions", [
        "Account Number", "Type", "Amount", "Balance After", "Date & Time"
        ]
)


# ==============================================
# 🧹 UTILITIES
# ==============================================

def normalize_headers(record):
    """Convert dictionary keys to lowercase with underscores."""
    return {k.lower().strip().replace(" ", "_"): v for k, v in record.items()}


def clean_account_numbers():
    """Clean account numbers by removing non-digit characters and ensuring uniqueness."""
    print("🔧 Cleaning account numbers...")
    records = [normalize_headers(r) for r in accounts_sheet.get_all_records()]
    used_numbers = set()

    for i, record in enumerate(records, start=2):
        raw_number = str(record.get("account_number", ""))
        cleaned = re.sub(r"\D", "", raw_number)
        if len(cleaned) < 10:
            cleaned = cleaned.rjust(10, "0")
        elif len(cleaned) > 10:
            cleaned = cleaned[:10]

        while cleaned in used_numbers or cleaned == "":
            cleaned = str(random.randint(1000000000, 9999999999))
        used_numbers.add(cleaned)

        if cleaned != raw_number:
            accounts_sheet.update_cell(i, 2, cleaned)
            print(f"✅ Fixed: {raw_number} → {cleaned}")

    print("🎉 Account numbers cleaned successfully!\n")


def log_transaction(account_number, t_type, amount, balance_after):
    """Log a transaction into the Google Sheet."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions_sheet.append_row(
        [account_number, t_type, f"{amount:.2f}", f"{balance_after:.2f}", timestamp]
    )


def safe_float(value):
    """Safely convert a string to a non-negative float."""
    cleaned = str(value).replace("£", "").replace(",", "").strip()
    try:
        amount = float(cleaned)
        if amount < 0:
            raise ValueError("Amount cannot be negative.")
        return amount
    except ValueError:
        raise ValueError(f"Invalid monetary value: {value}")


# ==============================================
# 💼 ACCOUNT OPERATIONS
# ==============================================

# def find_account(account_number):
#     """Find account by number."""
#     for i, raw in enumerate(accounts_sheet.get_all_records(), start=2):
#         acc = normalize_headers(raw)
#         if str(acc.get("account_number")) == str(account_number):
#             return i, acc
#     return None, None

def find_account(account_number):
    """Find account by number safely."""
    for i, raw in enumerate(accounts_sheet.get_all_records(), start=2):
        acc = normalize_headers(raw)
        if str(acc.get("account_number")) == str(account_number):
            try:
                acc["balance"] = float(str(acc.get("balance", 0)).replace("£", "").replace(",", ""))
            except ValueError:
                acc["balance"] = 0.0
            return i, acc
    return None, None


def generate_account_number():
    """Generate unique 10-digit account number."""
    while True:
        num = random.randint(1000000000, 9999999999)
        _, acc = find_account(num)
        if not acc:
            return num


def create_account(name, initial_balance):
    """Create new account."""
    print("🆕 Creating account...")
    acc_num = generate_account_number()
    accounts_sheet.append_row([name, acc_num, initial_balance])
    log_transaction(acc_num, "Account Created", initial_balance, initial_balance)
    print(f"✅ Account created successfully!\n   Account Number: {acc_num}")


def deposit(account_number, amount):
    """Deposit funds."""
    print("💰 Processing deposit...")
    row, acc = find_account(account_number)
    if not acc:
        print(f"❌ Account {account_number} not found.")
        return
    new_balance = float(acc.get("balance", 0)) + amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account_number, "Deposit", amount, new_balance)
    print(f"✅ Deposited £{amount:.2f}. New balance: £{new_balance:.2f}")


def withdraw(account_number, amount):
    """Withdraw funds."""
    print("💸 Processing withdrawal...")
    row, acc = find_account(account_number)
    if not acc:
        print(f"❌ Account {account_number} not found.")
        return
    balance = float(acc.get("balance", 0))
    if amount > balance:
        print(f"❌ Insufficient funds. Current balance: £{balance:.2f}")
        return
    new_balance = balance - amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account_number, "Withdrawal", amount, new_balance)
    print(f"✅ Withdrawal successful. New balance: £{new_balance:.2f}")


# ==============================================
# 📊 DISPLAY FUNCTIONS
# ==============================================

def display_balance(account_number):
    """Show account balance."""
    _, acc = find_account(account_number)
    if not acc:
        print(f"❌ Account {account_number} not found.")
        return
    print(f"📊 Current balance for {account_number}: £{float(acc.get('balance', 0)):.2f}")


def view_transaction_history(account_number):
    """Display last 10 transactions for an account."""
    print(f"\n📋 Transaction History — {account_number}")
    transactions = [normalize_headers(t) for t in transactions_sheet.get_all_records()]
    account_txs = [t for t in transactions if str(t.get("account_number")) == str(account_number)]

    if not account_txs:
        print("No transactions found for this account.")
        return

    for t in account_txs:
        if not t.get("date_&_time"):
            t["date_&_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    account_txs.sort(
        key=lambda x: datetime.strptime(
            x.get("date_&_time", "1970-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S"
        )
    )

    table = PrettyTable()
    table.field_names = ["Date & Time", "Type", "Amount", "Balance After"]

    for t in account_txs[-10:]:
        table.add_row([
            t.get("date_&_time"),
            t.get("type", "Unknown"),
            f"£{float(t.get('amount', 0)):.2f}",
            f"£{float(t.get('balance_after', 0)):.2f}"
        ])

    print(table)


def print_database():
    """Display all accounts (admin only)."""
    accounts = [normalize_headers(a) for a in accounts_sheet.get_all_records()]
    if not accounts:
        print("No accounts found.")
        return
    table = PrettyTable()
    table.field_names = ["Name", "Account Number", "Balance"]
    for a in accounts:
        table.add_row([a.get("name", "N/A"), a.get("account_number", "N/A"), f"£{float(a.get('balance', 0)):.2f}"])
    print(table)


# ==============================================
# 🧠 MENU
# ==============================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def get_choice():
    choice = input("Enter your choice: ").strip()
    if choice not in [str(i) for i in range(1, 8)]:
        print("❌ Invalid choice. Enter a number 1–7.")
        return None
    return choice


def main():
    clear_screen()
    print("=" * 30)
    print("🏦 Welcome to the Banking App")
    print("=" * 30)

    try:
        clean_account_numbers()

        while True:
            print("\nChoose an option:\n")
            print("1. Create Account")
            print("2. Withdraw Funds")
            print("3. Deposit Funds")
            print("4. Display Balance")
            print("5. View Transaction History")
            print("6. Print Database (Admin)")
            print("7. Exit")
            print("=" * 30)

            choice = get_choice()
            if not choice:
                continue

            try:
                if choice == "1":
                    name = input("Enter account name: ").strip()
                    if len(name) < 2:
                        raise ValueError("Name must be at least 2 characters.")
                    balance = safe_float(input("Enter initial balance (£): "))
                    create_account(name, balance)

                elif choice == "2":
                    acc = input("Enter account number: ").strip()
                    amt = safe_float(input("Enter withdrawal amount (£): "))
                    withdraw(acc, amt)

                elif choice == "3":
                    acc = input("Enter account number: ").strip()
                    amt = safe_float(input("Enter deposit amount (£): "))
                    deposit(acc, amt)

                elif choice == "4":
                    acc = input("Enter account number: ").strip()
                    display_balance(acc)

                elif choice == "5":
                    acc = input("Enter account number: ").strip()
                    view_transaction_history(acc)

                elif choice == "6":
                    admin_pw = input("Enter admin password: ")
                    if admin_pw != "admin123":  # change as needed
                        print("❌ Access denied.")
                        continue
                    print_database()

                elif choice == "7":
                    print("👋 Goodbye! Thanks for banking with us.")
                    break

            except ValueError as e:
                print(f"⚠️  Error: {e}")
            except Exception as e:
                print(f"💥 Unexpected error: {e}")

    except KeyboardInterrupt:
        print("\n👋 Session terminated by user.")
    except Exception as e:
        print(f"💥 Fatal error: {e}")


if __name__ == "__main__":
    main()
