import asyncio
import calendar
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

import gspread
from google.oauth2.service_account import Credentials
from mcp.server.mcpserver import MCPServer
from config import settings


ID_COLUMN = settings.expense_id_column
DATE_COLUMN = settings.expense_date_column
DESCRIPTION_COLUMN = settings.expense_description_column
CATEGORY_COLUMN = settings.expense_category_column
AMOUNT_COLUMN = settings.expense_amount_column
FIRST_DATA_ROW = settings.expense_first_data_row
SPREADSHEET_ID = settings.spreadsheet_id
WORKSHEET_NAME = settings.worksheet_name
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
INDONESIAN_MONTHS = {
    "Jan": "Jan",
    "Feb": "Feb",
    "Mar": "Mar",
    "Apr": "Apr",
    "Mei": "May",
    "Jun": "Jun",
    "Jul": "Jul",
    "Agu": "Aug",
    "Sep": "Sep",
    "Okt": "Oct",
    "Nov": "Nov",
    "Des": "Dec",
}
INDONESIAN_MONTH_NAMES = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
WIB = timezone(timedelta(hours=7), name="WIB")
TRANSACTION_ID_PATTERN = re.compile(r"^\d{6}-\d{2}$")
MAX_EXPENSE_AMOUNT = 100_000_000
REPORT_DASHBOARD_RANGE = settings.report_dashboard_range
BUDGET_WARNING_PERCENT = 80
BUDGET_TABLE_RANGE = settings.budget_table_range
BUDGET_PERIOD_RANGE = settings.budget_period_range

_sheet = None
_spreadsheet = None


def get_sheet():
    """Create the Sheets connection only when a tool is actually called."""
    global _sheet, _spreadsheet
    if _sheet is None:
        if not SPREADSHEET_ID:
            raise RuntimeError("SPREADSHEET_ID tidak ditemukan")
        credentials = Credentials.from_service_account_file(str(settings.google_credentials_path), scopes=SCOPES)
        client = gspread.authorize(credentials)
        _spreadsheet = client.open_by_key(SPREADSHEET_ID)
        _sheet = _spreadsheet.worksheet(WORKSHEET_NAME)
    return _sheet


def get_spreadsheet():
    """Return the workbook backing the spending sheet."""
    sheet = get_sheet()
    return _spreadsheet or getattr(sheet, "spreadsheet", None)


def make_transaction_id(date: str) -> str:
    """Create DDMMYY-NN, where NN is the expense order for that date."""
    try:
        date_key = datetime.strptime(date, "%d %b %Y").strftime("%d%m%y")
    except ValueError:
        date_key = datetime.now(WIB).strftime("%d%m%y")

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


def _valid_transaction_id(transaction_id: str) -> bool:
    return bool(TRANSACTION_ID_PATTERN.fullmatch(transaction_id.strip()))


def _format_record(record: dict) -> str:
    return (
        f"{record['transaction_id'] or '(tanpa Transaction ID)'} | {record['date']} | "
        f"{record['description']} | {record['category']} | Rp{record['amount']}"
    )


def _parse_expense_date(value: str) -> datetime:
    """Parse the English and Indonesian month labels used in the sheet."""
    parts = value.strip().split()
    if len(parts) == 3 and parts[1].title() in INDONESIAN_MONTHS:
        value = f"{parts[0]} {INDONESIAN_MONTHS[parts[1].title()]} {parts[2]}"
    try:
        return datetime.strptime(value, "%d %b %Y")
    except ValueError:
        return datetime.min


def _today_wib() -> date:
    return datetime.now(WIB).date()


def _parse_expense_amount(value: str) -> int:
    """Read Rupiah amounts stored as either plain or formatted sheet values."""
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else 0


def _parse_report_amount(value: object) -> Optional[int]:
    """Parse a numeric Report value without treating labels as zero."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    digits = re.sub(r"\D", "", text)
    return int(digits) if text and digits else None


def _normalise_report_label(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().rstrip(":").lower())


def _find_dashboard_metric(values: list[list[object]], label: str) -> Optional[int]:
    """Find the calculated value in a merged dashboard card by its label.

    Google Sheets returns only the top-left cell of each merged region.  A card
    label and its formula result therefore do not form a conventional two-column
    table.  We locate the label first, then use the nearest numeric cell in that
    card area.  The full dashboard range is read as formatted values, so formulas
    are returned as their calculated results rather than formula text.
    """
    normalized_label = _normalise_report_label(label)
    label_positions = [
        (row_index, column_index)
        for row_index, row in enumerate(values)
        for column_index, cell in enumerate(row)
        if _normalise_report_label(cell) == normalized_label
    ]
    if not label_positions:
        return None

    candidates: list[tuple[tuple[int, int, int, int], int]] = []
    for label_row, label_column in label_positions:
        for row_index, row in enumerate(values):
            for column_index, cell in enumerate(row):
                amount = _parse_report_amount(cell)
                if amount is None:
                    continue
                row_distance = abs(row_index - label_row)
                column_distance = abs(column_index - label_column)
                # A card value is normally directly below its label.  Retain a
                # small card neighbourhood so a value belonging to another card
                # (such as Budgeted Expenses) cannot be selected from afar.
                if row_distance > 3 or column_distance > 3:
                    continue
                direction_rank = 0 if column_distance == 0 and row_index > label_row else 1
                axis_rank = 0 if column_distance == 0 else 1 if row_distance == 0 else 2
                candidates.append(((row_distance + column_distance, direction_rank, axis_rank, row_index), amount))

    return min(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


def get_financial_balance() -> str:
    """Read actual income and spending cards from the Report dashboard."""
    balance_data = get_financial_balance_data()
    if isinstance(balance_data, str):
        return balance_data
    return (
        "Siap Bos.\n\n"
        f"Total Income: Rp{balance_data['income']:,}\n"
        f"Total Spending: Rp{balance_data['spending']:,}\n"
        f"Sisa Duit: Rp{balance_data['balance']:,}"
    )


def get_financial_balance_data() -> dict[str, int] | str:
    """Return Report dashboard figures for code that must not parse display text."""
    try:
        response = get_spreadsheet().values_get(
            REPORT_DASHBOARD_RANGE,
            params={"valueRenderOption": "FORMATTED_VALUE"},
        )
    except Exception as error:
        return f"Gagal membaca dashboard Report: {error}"

    values = response.get("values", []) if isinstance(response, dict) else []
    if not values:
        return "Data dashboard Report kosong atau tidak ditemukan."

    income = _find_dashboard_metric(values, "Total Income")
    spending = _find_dashboard_metric(values, "Total Spending")
    if income is None or spending is None:
        missing = "Total Income" if income is None else "Total Spending"
        return f"Nilai {missing} tidak ditemukan atau tidak valid di dashboard Report."

    # Actual balance is intentionally based on spending, never Budgeted Expenses.
    return {"income": income, "spending": spending, "balance": income - spending}


def _records_in_date_range(start_date: date, end_date: date) -> list[dict]:
    records = []
    for row_number, values in enumerate(get_sheet().get_all_values(), start=1):
        if row_number < FIRST_DATA_ROW:
            continue
        record = _record(row_number, values)
        transaction_date = _parse_expense_date(record["date"]).date()
        if start_date <= transaction_date <= end_date:
            records.append(record)
    return records


def _month_date_range(month: int, year: int, today: date) -> tuple[date, date]:
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])
    return start_date, min(end_date, today)


def _category_totals(records: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for record in records:
        category = record["category"] or "Tanpa kategori"
        totals[category] = totals.get(category, 0) + _parse_expense_amount(record["amount"])
    return totals


def _category_budgets() -> dict[str, tuple[str, int, int]]:
    """Read Allocation and Realization from the sheet's budget table."""
    response = get_spreadsheet().values_get(
        BUDGET_TABLE_RANGE, params={"valueRenderOption": "FORMATTED_VALUE"}
    )
    values = response.get("values", [])
    for row_index, row in enumerate(values):
        labels = [_normalise_report_label(value) for value in row]
        try:
            category_column = labels.index("expenses list")
            allocation_column = next(
                index for index, label in enumerate(labels) if label.startswith("allocation")
            )
            realization_column = next(
                index for index, label in enumerate(labels) if label.startswith(("realization", "realisation"))
            )
        except (ValueError, StopIteration):
            continue
        budgets = {}
        for data_row in values[row_index + 1:]:
            category = _cell(data_row, category_column + 1).strip()
            allocation = _parse_report_amount(_cell(data_row, allocation_column + 1))
            realization = _parse_report_amount(_cell(data_row, realization_column + 1)) or 0
            if category and allocation and allocation > 0:
                budgets[category.casefold()] = (category, allocation, realization)
        return budgets
    raise ValueError("Header Expenses List, Allocation, dan Realization tidak ditemukan di BUDGET_TABLE_RANGE")


def _budget_period() -> tuple[int, int]:
    """Read the year in K2 and month in K3 selected by the Report formulas."""
    response = get_spreadsheet().values_get(
        BUDGET_PERIOD_RANGE, params={"valueRenderOption": "FORMATTED_VALUE"}
    )
    values = response.get("values", [])
    try:
        year = int(str(values[0][0]).strip())
        month_value = str(values[1][0]).strip()
        month_names = {name.casefold(): index for index, name in enumerate(INDONESIAN_MONTH_NAMES, start=1)}
        month_names.update({name.casefold(): index for index, name in enumerate(calendar.month_name) if name})
        month = month_names.get(month_value.casefold()) or int(month_value)
    except (IndexError, TypeError, ValueError) as error:
        raise ValueError("Tahun/bulan budget di Report tidak valid") from error
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("Tahun/bulan budget di Report tidak valid")
    return year, month


def _budget_notice(category: str, transaction_date: str) -> str:
    parsed_date = _parse_expense_date(transaction_date)
    today = _today_wib()
    if parsed_date == datetime.min or (parsed_date.year, parsed_date.month) != (today.year, today.month):
        return ""
    try:
        year, month = _budget_period()
        if (year, month) != (parsed_date.year, parsed_date.month):
            return "\nInfo budget belum dicek: periode Report berbeda dari bulan transaksi."
        item = _category_budgets().get(category.casefold())
    except Exception:
        return "\nInfo budget belum bisa dibaca dari Report."
    if item is None:
        return ""
    _, budget, spent = item
    if spent >= budget:
        return f"\n⚠️ Budget {category} bulan ini terlewati: Rp{spent:,} dari Rp{budget:,}."
    if spent * 100 >= budget * BUDGET_WARNING_PERCENT:
        return f"\n⚠️ Budget {category} hampir habis: Rp{spent:,} dari Rp{budget:,} ({spent * 100 // budget}%)."
    return ""


def add_expense(date: str, description: str, category: str, amount: int) -> str:
    """Add an expense and return its generated Transaction ID."""
    if not isinstance(amount, int) or isinstance(amount, bool) or not 0 < amount <= MAX_EXPENSE_AMOUNT:
        return "Nominal expense harus berupa angka antara Rp1 dan Rp100.000.000."
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
    ) + _budget_notice(category, date)


def get_category_budgets() -> str:
    """Show the current allocation and realization from the sheet."""
    year, month = _budget_period()
    budgets = _category_budgets()
    if not budgets:
        return "Belum ada kategori dengan Allocation lebih dari nol di tabel budget."
    lines = [f"Budget kategori {INDONESIAN_MONTH_NAMES[month - 1]} {year} dari Report:"]
    for category, budget, spent in budgets.values():
        lines.append(f"- {category}: Rp{spent:,} / Rp{budget:,} ({spent * 100 // budget}%)")
    return "\n".join(lines)


def get_spending_date_range(start_date: str, end_date: str) -> str:
    """Summarize expenses for an inclusive ISO date range."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError):
        return "Tanggal harus berformat YYYY-MM-DD."
    if start > end:
        return "Tanggal awal tidak boleh setelah tanggal akhir."
    if (end - start).days > 366:
        return "Rentang tanggal maksimal 367 hari."
    records = _records_in_date_range(start, end)
    total = sum(_parse_expense_amount(record["amount"]) for record in records)
    lines = [
        f"Total pengeluaran {start:%d %b %Y}–{end:%d %b %Y}: Rp{total:,}",
        f"Jumlah transaksi: {len(records)}",
    ]
    if records:
        lines.extend(["", "Per kategori:"])
        lines.extend(
            f"- {category}: Rp{amount:,}"
            for category, amount in sorted(_category_totals(records).items(), key=lambda item: (-item[1], item[0]))
        )
    return "\n".join(lines)


def get_expense(transaction_id: str) -> str:
    """Get one expense by its Transaction ID."""
    if not _valid_transaction_id(transaction_id):
        return "Format Transaction ID tidak valid. Contoh: 260826-01."
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


def get_recent_expenses(limit: int = 10) -> str:
    """Get the most recent expenses, sorted by transaction date descending."""
    limit = max(1, min(limit, 50))
    records = [
        _record(row_number, values)
        for row_number, values in enumerate(get_sheet().get_all_values(), start=1)
        if row_number >= FIRST_DATA_ROW
        and any(
            _cell(values, column)
            for column in (DATE_COLUMN, DESCRIPTION_COLUMN, CATEGORY_COLUMN, AMOUNT_COLUMN)
        )
    ]
    records.sort(key=lambda record: (_parse_expense_date(record["date"]), record["row"]), reverse=True)
    if not records:
        return "Belum ada expense."
    return "\n".join(_format_record(record) for record in records[:limit])


def get_spending_summary(
    period: Literal["week", "month"] = "month",
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> str:
    """Return spending totals for a WIB week or a selected calendar month."""
    if period not in {"week", "month"}:
        return "Periode harus 'week' atau 'month'."

    today = _today_wib()
    if period == "week":
        if month is not None or year is not None:
            return "Rekap minggu hanya mendukung minggu berjalan. Gunakan period 'month' untuk memilih bulan."
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_label = "minggu ini"
    else:
        is_current_month_request = month is None and year is None
        target_year = year if year is not None else today.year
        target_month = month if month is not None else today.month
        if not isinstance(target_year, int) or not 2000 <= target_year <= 2100:
            return "Tahun harus berupa angka antara 2000 dan 2100."
        if not isinstance(target_month, int) or not 1 <= target_month <= 12:
            return "Bulan harus berupa angka 1 sampai 12."
        start_date = date(target_year, target_month, 1)
        end_date = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])
        end_date = min(end_date, today)
        period_label = (
            "bulan ini"
            if is_current_month_request
            else f"{INDONESIAN_MONTH_NAMES[target_month - 1]} {target_year}"
        )
    records = []
    for row_number, values in enumerate(get_sheet().get_all_values(), start=1):
        if row_number < FIRST_DATA_ROW:
            continue
        record = _record(row_number, values)
        transaction_date = _parse_expense_date(record["date"]).date()
        if start_date <= transaction_date <= end_date:
            records.append(record)

    date_range = f"{start_date.strftime('%d %b %Y')}–{end_date.strftime('%d %b %Y')}"
    if not records:
        return f"Belum ada pengeluaran untuk {period_label} ({date_range})."

    total = sum(_parse_expense_amount(record["amount"]) for record in records)
    category_totals = _category_totals(records)
    categories = sorted(category_totals.items(), key=lambda item: (-item[1], item[0]))
    category_lines = "\n".join(
        f"- {category}: Rp{amount:,}" for category, amount in categories
    )
    return (
        f"Total pengeluaran {period_label} ({date_range}): Rp{total:,}\n"
        f"Jumlah transaksi: {len(records)}\n\n"
        f"Per kategori:\n{category_lines}"
    )


def compare_monthly_spending(
    first_month: int,
    second_month: int,
    year: Optional[int] = None,
) -> str:
    """Compare total spending and categories between two months in one year."""
    today = _today_wib()
    target_year = year if year is not None else today.year
    if not isinstance(target_year, int) or not 2000 <= target_year <= 2100:
        return "Tahun harus berupa angka antara 2000 dan 2100."
    if not all(isinstance(month, int) and 1 <= month <= 12 for month in (first_month, second_month)):
        return "Bulan harus berupa angka 1 sampai 12."

    first_start, first_end = _month_date_range(first_month, target_year, today)
    second_start, second_end = _month_date_range(second_month, target_year, today)
    first_records = _records_in_date_range(first_start, first_end)
    second_records = _records_in_date_range(second_start, second_end)
    first_total = sum(_parse_expense_amount(record["amount"]) for record in first_records)
    second_total = sum(_parse_expense_amount(record["amount"]) for record in second_records)
    first_label = f"{INDONESIAN_MONTH_NAMES[first_month - 1]} {target_year}"
    second_label = f"{INDONESIAN_MONTH_NAMES[second_month - 1]} {target_year}"
    difference = first_total - second_total
    direction = "naik" if difference > 0 else "turun" if difference < 0 else "tetap"

    first_categories = _category_totals(first_records)
    second_categories = _category_totals(second_records)
    category_lines = []
    for category in sorted(set(first_categories) | set(second_categories)):
        first_amount = first_categories.get(category, 0)
        second_amount = second_categories.get(category, 0)
        change = first_amount - second_amount
        category_direction = "naik" if change > 0 else "turun" if change < 0 else "tetap"
        category_lines.append(
            f"- {category}: Rp{first_amount:,} vs Rp{second_amount:,} ({category_direction} Rp{abs(change):,})"
        )

    categories = "\n".join(category_lines) if category_lines else "- Belum ada transaksi di kedua bulan."
    return (
        f"Perbandingan {first_label} vs {second_label}\n"
        f"- {first_label}: Rp{first_total:,} ({len(first_records)} transaksi)\n"
        f"- {second_label}: Rp{second_total:,} ({len(second_records)} transaksi)\n"
        f"Selisih: {direction} Rp{abs(difference):,}\n\n"
        f"Per kategori:\n{categories}"
    )


def update_expense(
    transaction_id: str,
    date: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    amount: Optional[int] = None,
) -> str:
    """Update provided fields of an expense selected by Transaction ID."""
    if not _valid_transaction_id(transaction_id):
        return "Format Transaction ID tidak valid. Contoh: 260826-01."
    if amount is not None and (
        not isinstance(amount, int)
        or isinstance(amount, bool)
        or not 0 < amount <= MAX_EXPENSE_AMOUNT
    ):
        return "Nominal expense harus berupa angka antara Rp1 dan Rp100.000.000."
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
    updated = _find_expense(transaction_id)
    return f"Expense berhasil diperbarui: {_format_record(updated)}" + _budget_notice(updated["category"], updated["date"])


def delete_expense(transaction_id: str) -> str:
    """Permanently delete an expense selected by Transaction ID."""
    if not _valid_transaction_id(transaction_id):
        return "Format Transaction ID tidak valid. Contoh: 260826-01."
    record = _find_expense(transaction_id)
    if not record:
        return f"Expense dengan Transaction ID {transaction_id} tidak ditemukan."
    get_sheet().delete_rows(record["row"])
    return f"Expense {record['transaction_id']} berhasil dihapus."


server = MCPServer(name="spending-agent", version="1.1.0")
server.add_tool(add_expense, name="add_expense", description="Add an expense and return its Transaction ID.")
server.add_tool(get_expense, name="get_expense", description="Get an expense by its Transaction ID.")
server.add_tool(search_expenses, name="search_expenses", description="Search expenses by text, date, or category.")
server.add_tool(get_recent_expenses, name="get_recent_expenses", description="Get the latest expenses sorted by date, not sheet row order.")
server.add_tool(get_spending_summary, name="get_spending_summary", description="Get total spending and category totals for the current WIB week or current WIB month.")
server.add_tool(get_spending_date_range, name="get_spending_date_range", description="Summarize spending between inclusive start_date and end_date in YYYY-MM-DD format.")
server.add_tool(get_category_budgets, name="get_category_budgets", description="Show category Allocation and Realization from the budget table in Google Sheets.")
server.add_tool(compare_monthly_spending, name="compare_monthly_spending", description="Compare total spending and category totals for two selected months in the same year.")
server.add_tool(get_financial_balance, name="get_financial_balance", description="Read Total Income, Total Spending, and balance from Report!O8:P9.")
server.add_tool(update_expense, name="update_expense", description="Update an expense by its Transaction ID.")
server.add_tool(delete_expense, name="delete_expense", description="Delete an expense by its Transaction ID.")


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
