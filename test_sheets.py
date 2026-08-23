import gspread
from google.oauth2.service_account import Credentials

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

print("Spreadsheet:", spreadsheet.title)

for worksheet in spreadsheet.worksheets():
    print("Tab:", worksheet.title)