"""Financial report formatting built from the Sheets-backed server data layer."""

from datetime import date, datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

import server


DEFAULT_REPORT_TIMEZONE = "Asia/Jakarta"


class ReportDataError(RuntimeError):
    """Raised when a report cannot be completed from actual Sheet data."""


def report_timezone(name: str = DEFAULT_REPORT_TIMEZONE) -> ZoneInfo:
    """Return the configured IANA zone, defaulting to Jakarta."""
    return ZoneInfo(name)


def report_now(timezone_name: str = DEFAULT_REPORT_TIMEZONE) -> datetime:
    return datetime.now(report_timezone(timezone_name))


def _balance() -> dict[str, int]:
    data = server.get_financial_balance_data()
    if isinstance(data, str):
        raise ReportDataError(data)
    return data


def _records(start: date, end: date) -> list[dict]:
    return server._records_in_date_range(start, end)


def _total(records: list[dict]) -> int:
    return sum(server._parse_expense_amount(record["amount"]) for record in records)


def _largest_category(records: list[dict]) -> tuple[str, int] | None:
    totals = server._category_totals(records)
    return max(totals.items(), key=lambda item: (item[1], item[0])) if totals else None


def _category_line(records: list[dict]) -> str:
    category = _largest_category(records)
    return f"- {category[0]}: Rp{category[1]:,}" if category else "- Belum ada pengeluaran"


def build_daily_financial_report(now: datetime | None = None) -> str:
    now = now or report_now()
    today_records = _records(now.date(), now.date())
    month_records = _records(now.date().replace(day=1), now.date())
    balance = _balance()
    return (
        "📊 Financial Report\n\n"
        "Hari ini:\n"
        f"- Pengeluaran hari ini: Rp{_total(today_records):,}\n\n"
        "Bulan ini:\n"
        f"- Total Income: Rp{balance['income']:,}\n"
        f"- Total Spending: Rp{balance['spending']:,}\n"
        f"- Sisa Duit: Rp{balance['balance']:,}\n\n"
        "Kategori terbesar bulan ini:\n"
        f"{_category_line(month_records)}"
    )


def build_weekly_financial_report(now: datetime | None = None) -> str:
    now = now or report_now()
    end = now.date()
    start = end - timedelta(days=end.weekday())
    current = _records(start, end)
    previous_end = start - timedelta(days=1)
    previous = _records(previous_end - timedelta(days=6), previous_end)
    difference = _total(current) - _total(previous)
    direction = "naik" if difference > 0 else "turun" if difference < 0 else "tetap"
    balance = _balance()
    return (
        "📊 Weekly Financial Report\n\n"
        f"- Total spending minggu ini: Rp{_total(current):,}\n"
        f"- Dibanding minggu lalu: {direction} Rp{abs(difference):,}\n"
        f"- Kategori terbesar: {_category_line(current)[2:]}\n"
        f"- Total Income: Rp{balance['income']:,}\n"
        f"- Sisa Duit: Rp{balance['balance']:,}"
    )


def build_monthly_financial_report(now: datetime | None = None) -> str:
    now = now or report_now()
    current_start = now.date().replace(day=1)
    current = _records(current_start, now.date())
    previous_end = current_start - timedelta(days=1)
    previous = _records(previous_end.replace(day=1), previous_end)
    difference = _total(current) - _total(previous)
    direction = "naik" if difference > 0 else "turun" if difference < 0 else "tetap"
    balance = _balance()
    return (
        "📊 Monthly Financial Report\n\n"
        f"- Total Income: Rp{balance['income']:,}\n"
        f"- Total Spending: Rp{balance['spending']:,}\n"
        f"- Sisa Duit: Rp{balance['balance']:,}\n"
        f"- Kategori pengeluaran terbesar: {_category_line(current)[2:]}\n"
        f"- Total transaksi: {len(current)}\n"
        f"- Dibanding bulan lalu: {direction} Rp{abs(difference):,}"
    )


REPORT_BUILDERS: dict[str, Callable[[datetime | None], str]] = {
    "daily": build_daily_financial_report,
    "weekly": build_weekly_financial_report,
    "monthly": build_monthly_financial_report,
}
