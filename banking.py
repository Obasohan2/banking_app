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
        sheet = SHEET.add_worksheet(title=title, rows="1000", cols=str(len(headers)))
        sheet.append_row(headers)
    return sheet


accounts_sheet = get_or_create_worksheet(
    "accounts", ["Name", "Account Number", "Balance"]
)
transactions_sheet = get_or_create_worksheet(
    "transactions", ["Account Number", "Type", "Amount", "Balance After", "Date & Time"]
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

def find_account(account_number):
    """
    Find an account by number and return its row and details.
    Works even if the Balance header has symbols like (£) or ().
    """
    sheet = CLIENT.open("banking_app").worksheet("accounts")
    all_values = sheet.get_all_values()

    if not all_values or len(all_values) < 2:
        print("❌ No data found in the 'accounts' sheet.")
        return None, None

    # Normalize headers: lowercase, strip currency symbols and punctuation
    def normalize_header(h):
        return (
            h.lower()
            .replace("£", "")
            .replace("(", "")
            .replace(")", "")
            .replace("_", " ")
            .strip()
        )

    headers = [normalize_header(h) for h in all_values[0]]

    # Locate headers
    try:
        acc_index = headers.index("account number")
        # Accept "balance", "balance £", "balance ()", etc.
        bal_index = next(
            (i for i, h in enumerate(headers) if h.startswith("balance")), None
        )
        if bal_index is None:
            raise ValueError
    except ValueError:
        print("❌ Invalid sheet structure. Could not find 'Account Number' or 'Balance' columns.")
        print(f"Detected headers: {headers}")
        return None, None

    # Find the account
    for i, row in enumerate(all_values[1:], start=2):
        if str(row[acc_index]).replace(",", "").strip() == str(account_number).strip():
            name = row[0]
            try:
                balance = float(
                    str(row[bal_index]).replace("£", "").replace(",", "").strip() or 0
                )
            except ValueError:
                balance = 0.0
            return i, {
                "name": name,
                "account_number": account_number,
                "balance": balance,
            }

    print(f"❌ Account {account_number} not found.")
    return None, None


def generate_account_number():
    """Generate unique 10-digit account number."""
    while True:
        num = random.randint(1000000000, 9999999999)
        _, acc = find_account(num)
        if not acc:  # Ensure the account number is unique
            return num


def create_account(name, initial_balance):
    """Create a new account with proper balance formatting and confirmation."""
    print("🆕 Creating account...")

    # Always get the latest sheet
    sheet = CLIENT.open("banking_app").worksheet("accounts")

    # Generate a unique 10-digit account number
    acc_num = generate_account_number()

    # Ensure balance is stored as a float, not string
    balance = round(float(initial_balance), 2)

    # Add new row to the sheet
    sheet.append_row([name, acc_num, balance])

    # Log the creation
    log_transaction(acc_num, "Account Created", balance, balance)

    # Confirm creation
    print(f"✅ Account created successfully!")
    print(f"   👤 Name: {name}")
    print(f"   💳 Account Number: {acc_num}")
    print(f"   💰 Initial Balance: £{balance:.2f}")

    # Optional live verification
    all_accounts = [normalize_headers(a) for a in sheet.get_all_records()]
    created = next((a for a in all_accounts if str(a.get("account_number")) == str(acc_num)), None)
    if created:
        print("🔎 Verified in Google Sheets ✅")
    else:
        print("⚠️ Could not verify account creation in Google Sheets.")


# def deposit(account_number, amount):
#     """
#     Deposit funds and immediately display the new live balance.
#     """
#     print("💰 Processing deposit...")

#     sheet = CLIENT.open("banking_app").worksheet("accounts")
#     row, acc = find_account(account_number)
#     if not acc:
#         print(f"❌ Account {account_number} not found.")
#         return

#     new_balance = acc["balance"] + amount
#     sheet.update_cell(row, 3, new_balance)
#     log_transaction(account_number, "Deposit", amount, new_balance)

#     # ✅ Fetch updated balance directly from Google Sheets
#     all_values = sheet.get_all_values()
#     headers = [h.lower().strip() for h in all_values[0]]
#     bal_index = headers.index("balance")

#     try:
#         fresh_balance = float(str(all_values[row - 1][bal_index]).replace("£", "").replace(",", "").strip() or 0)
#     except ValueError:
#         fresh_balance = new_balance

#     print(f"✅ Deposit successful! New balance for {account_number}: £{fresh_balance:.2f}")

def deposit(account_number, amount):
    """
    Deposit funds with robust header detection and immediate confirmation.
    """
    print("💰 Processing deposit...")

    # Get live data
    sheet = CLIENT.open("banking_app").worksheet("accounts")
    all_values = sheet.get_all_values()
    headers = [h.lower().replace("£", "").replace("(", "").replace(")", "").strip() for h in all_values[0]]

    # Dynamically locate columns
    try:
        acc_index = headers.index("account number")
        bal_index = next((i for i, h in enumerate(headers) if h.startswith("balance")), None)
        if bal_index is None:
            raise ValueError("Could not find a balance column.")
    except ValueError as e:
        print(f"❌ Invalid sheet structure: {e}")
        print(f"Detected headers: {headers}")
        return

    # Find the account row
    for i, row in enumerate(all_values[1:], start=2):
        if str(row[acc_index]).replace(",", "").strip() == str(account_number).strip():
            try:
                balance = float(str(row[bal_index]).replace("£", "").replace(",", "").strip() or 0)
            except ValueError:
                balance = 0.0

            new_balance = balance + amount
            sheet.update_cell(i, bal_index + 1, new_balance)
            log_transaction(account_number, "Deposit", amount, new_balance)

            print(f"✅ Deposited £{amount:.2f}. New balance: £{new_balance:.2f}")
            return

    print(f"❌ Account {account_number} not found.")


def withdraw(account_number, amount):
    """
    Withdraw funds with dynamic header detection and live balance sync.
    """
    print("💸 Processing withdrawal...")

    sheet = CLIENT.open("banking_app").worksheet("accounts")
    all_values = sheet.get_all_values()

    # Normalize headers: remove £, parentheses, underscores, and spaces
    headers = [
        h.lower()
        .replace("£", "")
        .replace("(", "")
        .replace(")", "")
        .replace("_", " ")
        .strip()
        for h in all_values[0]
    ]

    # Locate headers dynamically
    try:
        acc_index = headers.index("account number")
        bal_index = next((i for i, h in enumerate(headers) if h.startswith("balance")), None)
        if bal_index is None:
            raise ValueError("Could not find a balance column.")
    except ValueError as e:
        print(f"❌ Invalid sheet structure: {e}")
        print(f"Detected headers: {headers}")
        return

    # Find matching account
    for i, row in enumerate(all_values[1:], start=2):
        if str(row[acc_index]).replace(",", "").strip() == str(account_number).strip():
            try:
                balance = float(str(row[bal_index]).replace("£", "").replace(",", "").strip() or 0)
            except ValueError:
                balance = 0.0

            if amount > balance:
                print(f"❌ Insufficient funds. Current balance: £{balance:.2f}")
                return

            new_balance = balance - amount
            sheet.update_cell(i, bal_index + 1, new_balance)
            log_transaction(account_number, "Withdrawal", amount, new_balance)

            print(f"✅ Withdrawal successful! £{amount:.2f} withdrawn.")
            print(f"💰 New balance for {account_number}: £{new_balance:.2f}")
            return

    print(f"❌ Account {account_number} not found.")


def display_balance(account_number):
    """
    Display the live balance for a specific account (handles header variations).
    """
    print("⏳ Fetching balance...")

    try:
        sheet = CLIENT.open("banking_app").worksheet("accounts")
        all_values = sheet.get_all_values()

        if not all_values or len(all_values) < 2:
            print("❌ No data found in the 'accounts' sheet.")
            return

        # Normalize headers: ignore £, parentheses, underscores, and case
        headers = [
            h.lower()
            .replace("£", "")
            .replace("(", "")
            .replace(")", "")
            .replace("_", " ")
            .strip()
            for h in all_values[0]
        ]

        # Dynamically locate relevant columns
        try:
            acc_index = headers.index("account number")
            bal_index = next((i for i, h in enumerate(headers) if h.startswith("balance")), None)
            if bal_index is None:
                raise ValueError("Balance column not found.")
        except ValueError as e:
            print(f"❌ Invalid sheet structure — {e}")
            print(f"Detected headers: {headers}")
            return

        # Find the account row and display balance
        for row in all_values[1:]:
            if str(row[acc_index]).replace(",", "").strip() == str(account_number).strip():
                try:
                    balance = float(str(row[bal_index]).replace("£", "").replace(",", "").strip() or 0)
                except ValueError:
                    balance = 0.0
                print(f"📊 Current balance for {account_number}: £{balance:.2f}")
                return

        print(f"❌ Account number '{account_number}' not found.")

    except Exception as e:
        print(f"💥 Unexpected error while fetching balance: {e}")

        

# ==============================================
# 📊 DISPLAY FUNCTIONS
# ==============================================

def view_transaction_history(account_number):
    """Display the last 10 transactions for an account."""
    print(f"\n📋 Transaction History — {account_number}")

    # Always get the latest transaction sheet
    sheet = CLIENT.open("banking_app").worksheet("transactions")
    transactions = [normalize_headers(t) for t in sheet.get_all_records()]

    # Filter for this account
    account_txs = [t for t in transactions if str(t.get("account_number")) == str(account_number)]

    if not account_txs:
        print("No transactions found for this account.")
        return

    # Sort by date (oldest to newest)
    for t in account_txs:
        if not t.get("date_&_time"):
            t["date_&_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    account_txs.sort(
        key=lambda x: datetime.strptime(
            x.get("date_&_time", "1970-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S"
        )
    )

    # Create formatted table
    table = PrettyTable()
    table.field_names = ["Date & Time", "Transaction Type", "Amount (£)", "Balance After (£)"]

    for t in account_txs[-10:]:  # show last 10
        try:
            amount = float(t.get("amount", 0))
            balance_after = float(t.get("balance_after", 0))
        except ValueError:
            amount = balance_after = 0.0

        table.add_row([
            t.get("date_&_time"),
            t.get("type", "Unknown"),
            f"£{amount:.2f}",
            f"£{balance_after:.2f}"
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
        table.add_row(
            [
                a.get("name", "N/A"),
                a.get("account_number", "N/A"),
                f"£{float(a.get('balance', 0)):.2f}",
            ]
        )
    print(table)


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
                else:
                    print("Invalid choice. Please try again.")

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
