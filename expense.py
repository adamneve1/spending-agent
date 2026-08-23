import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

credentials = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES,
)

client = gspread.authorize(credentials)

SPREADSHEET_ID = "1XjZarTjEsYOjUpIGgRsYcYac156Pwm7ZS5xHQjeJTck"

spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.worksheet("Spending")


def add_expense(description, category, amount):
    # Cari baris kosong berdasarkan kolom C
    dates = sheet.col_values(3)

    next_row = len(dates) + 1

    today = datetime.now().strftime("%d %b %Y")

    sheet.update_cell(next_row, 3, today)        # C = Date
    sheet.update_cell(next_row, 4, description)  # D = Description
    sheet.update_cell(next_row, 6, category)     # F = Category
    sheet.update_cell(next_row, 7, amount)       # G = Total

    print(f"Expense berhasil ditambahkan ke row {next_row}")


add_expense(
    description="TEST AI",
    category="Food",
    amount=25000000
)