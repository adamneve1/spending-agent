import asyncio
import os
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from mcp.server.mcpserver import MCPServer


# Column layout of the existing Spending sheet. The ID column is configurable.
ID_COLUMN = int(os.getenv("EXPENSE_ID_COLUMN", "1"))
DATE_COLUMN = 3
DESCRIPTION_COLUMN = 4
CATEGORY_COLUMN = 6
AMOUNT_COLUMN = 7
FIRST_DATA_ROW = 2
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1XjZarTjEsYOjUpIGgRsYcYac156Pwm7ZS5xHQjeJTck")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "Spending")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_sheet = None


def get_sheet():
    """Create the Sheets connection only when a tool is actually called."""
    global _sheet
    if _sheet is None:
        credentials = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        client = gspread.authorize(credentials)
        _sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    return _sheet


def make_transaction_id(date: str) -> str:
    """Create DDMMYY-NN, where NN is the expense order for that date."""
    try:
        date_key = datetime.strptime(date, "%d %b %Y").strftime("%d%m%y")
    except ValueError:
        date_key = datetime.now().strftime("%d%m%y")

    prefix = f"{date_key}-"
    existing_rows = get_sheet().get_all_values()
    same_day_count = sum(
        1
        for values in existing_rows[FIRST_DATA_ROW - 1 :]
        if _cell(values, DATE_COLUMN).strip() == date.strip()
    )
    existing_numbers = [
        int(transaction_id[len(prefix) :])
        for values in existing_rows[FIRST_DATA_ROW - 1 :]
        if (transaction_id := _cell(values, ID_COLUMN)).startswith(prefix)
        and transaction_id[len(prefix) :].isdigit()
    ]
    sequence = max([same_day_count, *existing_numbers], default=0) + 1
    return f"{prefix}{sequence:02d}"


def _cell(values: list[str], column: int) -> str:
    return values[column - 1] if len(values) >= column else ""


def _record(row_number: int, values: list[str]) -> dict:
    return {
        "row": row_number,
        "transaction_id": _cell(values, ID_COLUMN),
        "date": _cell(values, DATE_COLUMN),
        "description": _cell(values, DESCRIPTION_COLUMN),
        "category": _cell(values, CATEGORY_COLUMN),
        "amount": _cell(values, AMOUNT_COLUMN),
    }


def _find_expense(transaction_id: str) -> Optional[dict]:
    wanted_id = transaction_id.strip().upper()
    for row_number, values in enumerate(get_sheet().get_all_values(), start=1):
        if row_number >= FIRST_DATA_ROW and _cell(values, ID_COLUMN).strip().upper() == wanted_id:
            return _record(row_number, values)
    return None


def _format_record(record: dict) -> str:
    return (
        f"{record['transaction_id'] or '(tanpa Transaction ID)'} | {record['date']} | "
        f"{record['description']} | {record['category']} | Rp{record['amount']}"
    )


def add_expense(date: str, description: str, category: str, amount: int) -> str:
    """Add an expense and return its generated Transaction ID."""
    sheet = get_sheet()
    next_row = len(sheet.col_values(DATE_COLUMN)) + 1
    transaction_id = make_transaction_id(date)
    # Apostrophe makes Google Sheets keep IDs beginning with 0 as text.
    sheet.update_cell(next_row, ID_COLUMN, f"'{transaction_id}")
    sheet.update_cell(next_row, DATE_COLUMN, date)
    sheet.update_cell(next_row, DESCRIPTION_COLUMN, description)
    sheet.update_cell(next_row, CATEGORY_COLUMN, category)
    sheet.update_cell(next_row, AMOUNT_COLUMN, amount)
    return (
        f"Expense berhasil ditambahkan. Transaction ID: {transaction_id} | "
        f"{date} | {description} | {category} | Rp{amount:,}"
    )


def get_expense(transaction_id: str) -> str:
    """Get one expense by its Transaction ID."""
    record = _find_expense(transaction_id)
    if not record:
        return f"Expense dengan Transaction ID {transaction_id} tidak ditemukan."
    return _format_record(record)


def search_expenses(
    query: Optional[str] = None,
    date: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Search expenses by text, exact date, or category. Returns at most 50."""
    limit = max(1, min(limit, 50))
    query, date, category = (query or "").strip().lower(), (date or "").strip().lower(), (category or "").strip().lower()
    matches = []
    for row_number, values in enumerate(get_sheet().get_all_values(), start=1):
        if row_number < FIRST_DATA_ROW or not any(
            _cell(values, column)
            for column in (DATE_COLUMN, DESCRIPTION_COLUMN, CATEGORY_COLUMN, AMOUNT_COLUMN)
        ):
            continue
        record = _record(row_number, values)
        searchable = " ".join(str(value).lower() for key, value in record.items() if key != "row")
        if (query and query not in searchable) or (date and date != record["date"].lower()) or (category and category != record["category"].lower()):
            continue
        matches.append(record)
        if len(matches) >= limit:
            break
    return "\n".join(_format_record(record) for record in matches) if matches else "Tidak ada expense yang cocok."


def update_expense(
    transaction_id: str,
    date: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    amount: Optional[int] = None,
) -> str:
    """Update provided fields of an expense selected by Transaction ID."""
    record = _find_expense(transaction_id)
    if not record:
        return f"Expense dengan Transaction ID {transaction_id} tidak ditemukan."
    changes = ((DATE_COLUMN, date), (DESCRIPTION_COLUMN, description), (CATEGORY_COLUMN, category), (AMOUNT_COLUMN, amount))
    changed = False
    for column, value in changes:
        if value is not None:
            get_sheet().update_cell(record["row"], column, value)
            changed = True
    if not changed:
        return "Tidak ada perubahan yang diberikan."
    return f"Expense berhasil diperbarui: {_format_record(_find_expense(transaction_id))}"


def delete_expense(transaction_id: str) -> str:
    """Permanently delete an expense selected by Transaction ID."""
    record = _find_expense(transaction_id)
    if not record:
        return f"Expense dengan Transaction ID {transaction_id} tidak ditemukan."
    get_sheet().delete_rows(record["row"])
    return f"Expense {record['transaction_id']} berhasil dihapus."


server = MCPServer(name="spending-agent", version="1.1.0")
server.add_tool(add_expense, name="add_expense", description="Add an expense and return its Transaction ID.")
server.add_tool(get_expense, name="get_expense", description="Get an expense by its Transaction ID.")
server.add_tool(search_expenses, name="search_expenses", description="Search expenses by text, date, or category.")
server.add_tool(update_expense, name="update_expense", description="Update an expense by its Transaction ID.")
server.add_tool(delete_expense, name="delete_expense", description="Delete an expense by its Transaction ID.")


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
