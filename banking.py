import gspread
from google.oauth2.service_account import Credentials
import random

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
    
    
