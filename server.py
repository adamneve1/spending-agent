import asyncio
import gspread

from google.oauth2.service_account import Credentials
from mcp.server.mcpserver import MCPServer


# =========================
# Google Sheets
# =========================

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


# =========================
# Expense Function
# =========================

def add_expense(
    date: str,
    description: str,
    category: str,
    amount: int,
) -> str:
    """
    Add an expense to the Spending Google Sheet.

    Date format: DD Mon YYYY
    Example: 05 Aug 2026
    """

    dates = sheet.col_values(3)

    next_row = len(dates) + 1

    sheet.update_cell(next_row, 3, date)
    sheet.update_cell(next_row, 4, description)
    sheet.update_cell(next_row, 6, category)
    sheet.update_cell(next_row, 7, amount)

    return (
        f"Expense berhasil ditambahkan: "
        f"{date} | {description} | {category} | Rp{amount:,}"
    )


# =========================
# MCP Server
# =========================

server = MCPServer(
    name="spending-agent",
    version="1.0.0",
)

server.add_tool(
    add_expense,
    name="add_expense",
    description="Add an expense to the Spending Google Sheet.",
)


# =========================
# Run
# =========================

async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())