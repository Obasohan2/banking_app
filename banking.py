import gspread
from google.oauth2.service_account import Credentials
import random
from prettytable import PrettyTable


SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
    ]

CREDS = Credentials.from_service_account_file('creds.json')
SCOPED_CREDS = CREDS.with_scopes(SCOPE)
GSPREAD_CLIENT = gspread.authorize(SCOPED_CREDS)
SHEET = GSPREAD_CLIENT.open('banking_app')

# Access the sheet
accounts_sheet = SHEET.worksheet("accounts")


def print_database():
    """
    Print all accounts in the database in a formatted table.
    """
    accounts = accounts_sheet.get_all_records()
    if not accounts:
        print("No accounts found in the database.")
        return

    # Create a PrettyTable instance
    table = PrettyTable()
    table.field_names = ["Name", "Account Number", "Balance"]

    for account in accounts:
        table.add_row([
            account['Name'], account['Account Number'], account['Balance']
        ])

    print(table)


def is_money(value):
    """Check if a string can be converted to a float."""
    try:
        float(value)
        return True
    except ValueError:
        return False


def find_account(account_number):
    """Find an account by account number."""
    accounts = accounts_sheet.get_all_records()
    for index, account in enumerate(accounts):
        if str(account['Account Number']) == str(account_number):
            return index + 2, account  # Row number and account details
    return None, None


def generate_account_number():
    """Generate a unique 10-digit account number."""
    while True:
        account_number = random.randint(1000000000, 9999999999)
        _, account = find_account(account_number)
        if not account:
            return account_number


def create_account(name, initial_balance):
    """Create a new account."""
    print("Creating account...")
    account_number = generate_account_number()
    accounts_sheet.append_row([name, account_number, float(initial_balance)])
    print(f"✅ Account created successfully. Account Number: {account_number}")
    
    
def main():
    print("==========================")
    print("Welcome to the Banking App")
    print("==========================")

    while True:
        print("\nSelect an option:\n")
        print("1. Create Account")
        print("2. Withdraw Funds")
        print("3. Deposit Funds")
        print("4. Display Balance")
        print("5. Print Database")
        print("6. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            name = input("Enter Account Name: ")
            initial_balance = input("Enter initial balance (£): ")
            if not is_money(initial_balance):
                print("❌ Invalid balance amount.")
                continue
            create_account(name, float(initial_balance))

        elif choice == "2":
            account_number = input("Enter account number: ")
            amount = input("Enter withdrawal amount (£): ")
            if not is_money(amount):
                print("❌ Invalid amount.")
                continue
            withdraw(account_number, float(amount))

        elif choice == "3":
            account_number = input("Enter account number: ")
            amount = input("Enter deposit amount (£): ")
            if not is_money(amount):
                print("❌ Invalid amount.")
                continue
            deposit(account_number, float(amount))

        elif choice == "4":
            account_number = input("Enter account number: ")
            display_balance(account_number)

        elif choice == "5":
            print_database()

        elif choice == "6":
            print("👋 Exiting the application. Goodbye!")
            break

        else:
            print("❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    main()