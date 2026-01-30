import gspread
from google.oauth2.service_account import Credentials
import os
import json
import base64

# ==============================================
# 🔧 GOOGLE SHEETS SETUP (HEROKU SAFE)
# ==============================================

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

CREDS_BASE64 = os.environ.get("CREDS_BASE64")

if not CREDS_BASE64:
    raise RuntimeError(
        "CREDS_BASE64 environment variable not set. "
        "Set it on Heroku before running the app."
    )

decoded_creds = base64.b64decode(CREDS_BASE64).decode("utf-8")
creds_dict = json.loads(decoded_creds)

CREDS = Credentials.from_service_account_info(creds_dict)
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
    "transactions",
    ["Account Number", "Type", "Amount", "Balance After", "Date & Time"]
)

# ==============================================
# 🧹 UTILITIES
# ==============================================


def normalize_headers(record):
    """Convert dictionary keys to lowercase with underscores."""
    return {k.lower().strip().replace(" ", "_"): v for k, v in record.items()}


def clean_account_numbers():
    """Remove non-digits and duplicates from account numbers."""
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
        [
            account_number,
            t_type,
            f"{amount:.2f}",
            f"{balance_after:.2f}",
            timestamp,
        ]
    )


def safe_float(value):
    """Safely convert a string to a non-negative float."""
    cleaned = str(value).replace("£", "").replace(",", "").strip()
    try:
        amount = float(cleaned)
        if amount < 0:
            raise ValueError
        return amount
    except ValueError:
        raise ValueError(f"Invalid monetary value: {value}")


# ==============================================
# 💼 ACCOUNT OPERATIONS
# ==============================================


def find_account(account_number):
    """Find an account by number and return its row and details."""
    sheet = CLIENT.open("banking_app").worksheet("accounts")
    all_values = sheet.get_all_values()

    if len(all_values) < 2:
        return None, None

    headers = [
        h.lower().replace("£", "").replace("(", "").replace(")", "").strip()
        for h in all_values[0]
    ]

    acc_index = headers.index("account number")
    bal_index = next(i for i, h in enumerate(headers) if h.startswith("balance"))

    for i, row in enumerate(all_values[1:], start=2):
        if row[acc_index].strip() == str(account_number).strip():
            balance = float(row[bal_index].replace("£", "").replace(",", "") or 0)
            return i, {"account_number": account_number, "balance": balance}

    return None, None


def generate_account_number():
    """Generate unique 10-digit account number."""
    while True:
        num = random.randint(1000000000, 9999999999)
        _, acc = find_account(num)
        if not acc:
            return num


def create_account(name, initial_balance):
    print("🆕 Creating account...")
    sheet = CLIENT.open("banking_app").worksheet("accounts")

    acc_num = generate_account_number()
    balance = round(float(initial_balance), 2)

    sheet.append_row([name, acc_num, balance])
    log_transaction(acc_num, "Account Created", balance, balance)

    print("✅ Account created successfully!")
    print(f"👤 Name: {name}")
    print(f"💳 Account Number: {acc_num}")
    print(f"💰 Balance: £{balance:.2f}")


def deposit(account_number, amount):
    print("💰 Processing deposit...")
    sheet = CLIENT.open("banking_app").worksheet("accounts")
    all_values = sheet.get_all_values()

    headers = [
        h.lower().replace("£", "").replace("(", "").replace(")", "").strip()
        for h in all_values[0]
    ]

    acc_index = headers.index("account number")
    bal_index = next(i for i, h in enumerate(headers) if h.startswith("balance"))

    for i, row in enumerate(all_values[1:], start=2):
        if row[acc_index].strip() == str(account_number).strip():
            balance = float(row[bal_index].replace("£", "").replace(",", "") or 0)
            new_balance = balance + amount
            sheet.update_cell(i, bal_index + 1, new_balance)
            log_transaction(account_number, "Deposit", amount, new_balance)
            print(f"✅ Deposited £{amount:.2f} | New balance £{new_balance:.2f}")
            return

    print("❌ Account not found.")


def withdraw(account_number, amount):
    print("💸 Processing withdrawal...")
    sheet = CLIENT.open("banking_app").worksheet("accounts")
    all_values = sheet.get_all_values()

    headers = [
        h.lower().replace("£", "").replace("(", "").replace(")", "").strip()
        for h in all_values[0]
    ]

    acc_index = headers.index("account number")
    bal_index = next(i for i, h in enumerate(headers) if h.startswith("balance"))

    for i, row in enumerate(all_values[1:], start=2):
        if row[acc_index].strip() == str(account_number).strip():
            balance = float(row[bal_index].replace("£", "").replace(",", "") or 0)

            if amount > balance:
                print("❌ Insufficient funds.")
                return

            new_balance = balance - amount
            sheet.update_cell(i, bal_index + 1, new_balance)
            log_transaction(account_number, "Withdrawal", amount, new_balance)
            print(f"✅ Withdrawn £{amount:.2f} | New balance £{new_balance:.2f}")
            return

    print("❌ Account not found.")


def display_balance(account_number):
    print("⏳ Fetching balance...")
    _, acc = find_account(account_number)
    if acc:
        print(f"💰 Balance: £{acc['balance']:.2f}")
    else:
        print("❌ Account not found.")


def view_transaction_history(account_number):
    print(f"\n📋 Transaction History — {account_number}")
    sheet = CLIENT.open("banking_app").worksheet("transactions")
    rows = sheet.get_all_values()[1:]

    table = PrettyTable()
    table.field_names = ["Date", "Type", "Amount (£)", "Balance (£)"]

    for row in rows:
        if row[0] == str(account_number):
            table.add_row([row[4], row[1], row[2], row[3]])

    print(table)


def print_database():
    print("📂 Full Account List")
    sheet = CLIENT.open("banking_app").worksheet("accounts")
    rows = sheet.get_all_values()[1:]

    table = PrettyTable()
    table.field_names = ["Name", "Account", "Balance (£)"]

    for row in rows:
        table.add_row(row)

    print(table)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def get_choice():
    choice = input("Enter your choice: ").strip()
    return choice if choice in [str(i) for i in range(1, 8)] else None


def main():
    clear_screen()
    print("🏦 Welcome to the Banking App")

    clean_account_numbers()

    while True:
        print("""
1. Create Account
2. Withdraw Funds
3. Deposit Funds
4. Display Balance
5. View Transaction History
6. Print Database (Admin)
7. Exit
""")

        choice = get_choice()

        if choice == "1":
            name = input("Name: ")
            balance = safe_float(input("Initial balance: "))
            create_account(name, balance)

        elif choice == "2":
            acc = input("Account number: ")
            amt = safe_float(input("Amount: "))
            withdraw(acc, amt)

        elif choice == "3":
            acc = input("Account number: ")
            amt = safe_float(input("Amount: "))
            deposit(acc, amt)

        elif choice == "4":
            acc = input("Account number: ")
            display_balance(acc)

        elif choice == "5":
            acc = input("Account number: ")
            view_transaction_history(acc)

        elif choice == "6":
            pw = input("Admin password: ")
            if pw == "admin123":
                print_database()
            else:
                print("❌ Access denied")

        elif choice == "7":
            print("👋 Goodbye!")
            break

        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    main()
