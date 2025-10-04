import gspread
from google.oauth2.service_account import Credentials
import random
from prettytable import PrettyTable
from datetime import datetime
import re


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


accounts_sheet = get_or_create_worksheet("accounts", ["Name", "Account Number", "Balance"])
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
    """Ensure all account numbers are valid 10-digit numbers."""
    print("🔧 Checking and cleaning account numbers...")

    records = [normalize_headers(r) for r in accounts_sheet.get_all_records()]
    used_numbers = set()

    for i, record in enumerate(records, start=2):
        raw = str(record.get("account_number", ""))
        clean = re.sub(r"\D", "", raw)

        if len(clean) != 10:
            clean = str(random.randint(1000000000, 9999999999))

        while clean in used_numbers:
            clean = str(random.randint(1000000000, 9999999999))
        used_numbers.add(clean)

        if clean != raw:
            accounts_sheet.update_cell(i, 2, clean)
            print(f"✅ Fixed account for {record.get('name', 'Unknown')}: {raw} → {clean}")

    print("🎉 Account number cleaning complete!\n")


def log_transaction(account_number, t_type, amount, balance_after):
    """Log a transaction into the Google Sheet."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions_sheet.append_row([account_number, t_type, amount, balance_after, timestamp])


# ==============================================
# 🧾 VALIDATION
# ==============================================

def validate_name(name):
    if not name or len(name.strip()) < 2:
        raise ValueError("Name must contain at least 2 characters.")
    return name.strip()


def validate_account_number(acc_num):
    if not acc_num.isdigit() or len(acc_num) != 10:
        raise ValueError("Account number must be exactly 10 digits.")
    return acc_num


def safe_float(value):
    try:
        val = float(value)
        if val < 0:
            raise ValueError
        return val
    except (ValueError, TypeError):
        raise ValueError(f"Invalid amount '{value}'. Enter a positive number.")


# ==============================================
# 💼 ACCOUNT OPERATIONS
# ==============================================

def find_account(account_number):
    """Find account by number safely (case-insensitive headers)."""
    for i, raw in enumerate(accounts_sheet.get_all_records(), start=2):
        acc = normalize_headers(raw)
        if str(acc.get("account_number")) == str(account_number):
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
    print(f"✅ Deposited £{amount}. New balance: £{new_balance}")


def withdraw(account_number, amount):
    """Withdraw funds."""
    print("💸 Processing withdrawal...")
    row, acc = find_account(account_number)
    if not acc:
        print(f"❌ Account {account_number} not found.")
        return
    balance = float(acc.get("balance", 0))
    if amount > balance:
        print(f"❌ Insufficient funds. Current balance: £{balance}")
        return
    new_balance = balance - amount
    accounts_sheet.update_cell(row, 3, new_balance)
    log_transaction(account_number, "Withdrawal", amount, new_balance)
    print(f"✅ Withdrawal successful. New balance: £{new_balance}")


# ==============================================
# 📊 DISPLAY FUNCTIONS
# ==============================================

def display_balance(account_number):
    """Show account balance."""
    _, acc = find_account(account_number)
    if not acc:
        print(f"❌ Account {account_number} not found.")
        return
    print(f"📊 Current balance for {account_number}: £{acc.get('balance', 0)}")


def view_transaction_history(account_number):
    """Display recent transactions (header-insensitive, auto-fills missing timestamps, sorted by date)."""
    print(f"\n📋 Transaction History — {account_number}")

    # Normalize headers for all transaction records
    transactions = [normalize_headers(t) for t in transactions_sheet.get_all_records()]
    account_txs = [t for t in transactions if str(t.get("account_number")) == str(account_number)]

    if not account_txs:
        print("No transactions found for this account.")
        return

    # Fill missing timestamps with current time
    for t in account_txs:
        if not t.get("date_&_time"):
            t["date_&_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sort transactions by actual date/time (oldest to newest)
    account_txs.sort(
        key=lambda x: datetime.strptime(x.get("date_&_time", ""), "%Y-%m-%d %H:%M:%S")
    )

    # Prepare display table
    table = PrettyTable()
    table.field_names = ["Date & Time", "Type", "Amount", "Balance After"]

    for t in account_txs[-10:]:  # show last 10 transactions
        date_time = t.get("date_&_time")
        tx_type = t.get("type", "Unknown")
        amount = f"£{t.get('amount', 0)}"
        balance_after = f"£{t.get('balance_after', 0)}"
        table.add_row([date_time, tx_type, amount, balance_after])

    print(table)


def print_database():
    """Display all accounts (safe header handling)."""
    accounts = [normalize_headers(a) for a in accounts_sheet.get_all_records()]
    if not accounts:
        print("No accounts found.")
        return
    table = PrettyTable()
    table.field_names = ["Name", "Account Number", "Balance"]
    for a in accounts:
        table.add_row([a.get("name", "N/A"), a.get("account_number", "N/A"), a.get("balance", "N/A")])
    print(table)


# ==============================================
# 🧠 MENU
# ==============================================

def get_choice():
    """Get validated menu selection."""
    choice = input("Enter your choice: ").strip()
    if choice not in [str(i) for i in range(1, 8)]:
        print("❌ Invalid choice. Enter a number 1–7.")
        return None
    return choice


def main():
    print("=" * 30) 
    print("🏦 Welcome to the Banking App")
    print("=" * 30)

    try:
        clean_account_numbers()

        while True:
            print("\nChoose an option:\n")
            print("=" * 30) 
            print("1. Create Account")
            print("=" * 30) 
            print("2. Withdraw Funds")
            print("=" * 30) 
            print("3. Deposit Funds")
            print("=" * 30) 
            print("4. Display Balance")
            print("=" * 30) 
            print("5. View Transaction History")
            print("=" * 30) 
            print("6. Print Database (Admin)")
            print("=" * 30) 
            print("7. Exit")
            print("=" * 30) 

            choice = get_choice()
            if not choice:
                continue

            try:
                if choice == "1":
                    name = validate_name(input("Enter account name: "))
                    balance = safe_float(input("Enter initial balance (£): "))
                    create_account(name, balance)

                elif choice == "2":
                    acc = validate_account_number(input("Enter account number: "))
                    amt = safe_float(input("Enter withdrawal amount (£): "))
                    withdraw(acc, amt)

                elif choice == "3":
                    acc = validate_account_number(input("Enter account number: "))
                    amt = safe_float(input("Enter deposit amount (£): "))
                    deposit(acc, amt)

                elif choice == "4":
                    acc = validate_account_number(input("Enter account number: "))
                    display_balance(acc)

                elif choice == "5":
                    acc = validate_account_number(input("Enter account number: "))
                    view_transaction_history(acc)

                elif choice == "6":
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
