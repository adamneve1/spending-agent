import re
import sys
from datetime import date
from pathlib import Path

# GitHub Actions may collect tests with only the tests directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


class FakeSheet:
    def __init__(self):
        self.rows = [["", "Transaction ID", "Date", "Description", "", "Category", "Amount"]]

    def col_values(self, column):
        return [row[column - 1] if len(row) >= column else "" for row in self.rows]

    def update_cell(self, row, column, value):
        while len(self.rows) < row:
            self.rows.append([])
        while len(self.rows[row - 1]) < column:
            self.rows[row - 1].append("")
        value = str(value)
        self.rows[row - 1][column - 1] = value[1:] if value.startswith("'") else value

    def get_all_values(self):
        return self.rows

    def delete_rows(self, row):
        del self.rows[row - 1]


def setup_function():
    server._sheet = FakeSheet()
    server._spreadsheet = FakeSpreadsheet([["Expenses List", "Allocation", "Realization"]])


class FakeSpreadsheet:
    def __init__(self, values, period=None):
        self.values = values
        self.period = period or [["2026"], ["August"]]
        self.requested_ranges = []

    def values_get(self, cell_range, params=None):
        self.requested_ranges.append(cell_range)
        return {"values": self.period if cell_range == server.BUDGET_PERIOD_RANGE else self.values}


def test_add_creates_id_and_get_finds_expense():
    result = server.add_expense("05 Aug 2026", "Makan siang", "Food", 25000)
    transaction_id = re.search(r"\d{6}-\d{2}", result).group(0)

    assert "Transaction ID" in result
    assert transaction_id in server.get_expense(transaction_id.lower())
    assert "Makan siang" in server.get_expense(transaction_id)


def test_ids_use_date_and_increment_for_same_day():
    first = server.add_expense("05 Aug 2026", "Sarapan", "Food", 10000)
    second = server.add_expense("05 Aug 2026", "Makan siang", "Food", 25000)

    assert "050826-01" in first
    assert "050826-02" in second


def test_balance_reads_merged_dashboard_cards_and_ignores_budgeted_expenses():
    # Each card's value is on the row below its label, as Google Sheets exposes
    # merged cells: only the top-left cell of each merged region has a value.
    report = FakeSpreadsheet([
        ["", "Total Income", "", "", "Budgeted Expenses", "", "", "Total Spending"],
        ["", "Rp5.747.875", "", "", "Rp2.313.000", "", "", "Rp2.548.500"],
        ["", "Monthly Savings", "", "", "Sisa Duit"],
        ["", "Rp0", "", "", "Rp3.199.375"],
    ])
    server._spreadsheet = report

    result = server.get_financial_balance()

    assert report.requested_ranges == [server.REPORT_DASHBOARD_RANGE]
    assert "Total Income: Rp5,747,875" in result
    assert "Total Spending: Rp2,548,500" in result
    assert "Sisa Duit: Rp3,199,375" in result
    assert "Rp3,434,875" not in result
    assert report.values == [
        ["", "Total Income", "", "", "Budgeted Expenses", "", "", "Total Spending"],
        ["", "Rp5.747.875", "", "", "Rp2.313.000", "", "", "Rp2.548.500"],
        ["", "Monthly Savings", "", "", "Sisa Duit"],
        ["", "Rp0", "", "", "Rp3.199.375"],
    ]


def test_balance_rejects_empty_or_invalid_report_data():
    server._spreadsheet = FakeSpreadsheet([])
    assert "dashboard Report kosong" in server.get_financial_balance()

    server._spreadsheet = FakeSpreadsheet([["Total Income"], ["Total Spending", "bukan nominal"]])
    assert "Total Income tidak ditemukan atau tidak valid" in server.get_financial_balance()


def test_recent_expenses_are_sorted_by_date_not_sheet_row():
    server.add_expense("02 Jan 2026", "Telur", "Food", 22000)
    server.add_expense("26 Aug 2026", "Bensin", "Bensin", 35000)
    server.add_expense("03 Jan 2026", "Kopi", "Food", 10000)

    result = server.get_recent_expenses(limit=2)

    assert "Bensin" in result.splitlines()[0]
    assert "Kopi" in result.splitlines()[1]


def test_search_update_and_delete_expense():
    result = server.add_expense("05 Aug 2026", "Makan siang", "Food", 25000)
    transaction_id = re.search(r"\d{6}-\d{2}", result).group(0)

    assert transaction_id in server.search_expenses(category="food")
    assert "Makan malam" in server.update_expense(transaction_id, description="Makan malam", amount=30000)
    assert "Rp30000" in server.get_expense(transaction_id)
    assert "berhasil dihapus" in server.delete_expense(transaction_id)
    assert "tidak ditemukan" in server.get_expense(transaction_id)


def test_update_requires_a_real_change_and_unknown_id_is_safe():
    assert "tidak ditemukan" in server.delete_expense("010126-99")
    result = server.add_expense("05 Aug 2026", "Kopi", "Food", 10000)
    transaction_id = re.search(r"\d{6}-\d{2}", result).group(0)
    assert server.update_expense(transaction_id) == "Tidak ada perubahan yang diberikan."


def test_rejects_invalid_transaction_ids_and_amounts():
    assert "Format Transaction ID tidak valid" in server.get_expense("invalid")
    assert "Nominal expense harus" in server.add_expense("05 Aug 2026", "Kopi", "Food", 0)


def test_spending_summary_for_current_week_and_month(monkeypatch):
    monkeypatch.setattr(server, "_today_wib", lambda: date(2026, 8, 28))
    server.add_expense("03 Aug 2026", "Kopi lama", "Food", 10000)
    server.add_expense("24 Aug 2026", "Makan", "Food", 25000)
    server.add_expense("27 Aug 2026", "Bensin", "Bensin", 35000)
    server.add_expense("29 Aug 2026", "Masa depan", "Food", 50000)

    week = server.get_spending_summary("week")
    month = server.get_spending_summary("month")

    assert "Total pengeluaran minggu ini (24 Aug 2026–28 Aug 2026): Rp60,000" in week
    assert "Food: Rp25,000" in week
    assert "Bensin: Rp35,000" in week
    assert "Total pengeluaran bulan ini (01 Aug 2026–28 Aug 2026): Rp70,000" in month
    assert "Jumlah transaksi: 3" in month


def test_spending_summary_for_a_selected_month(monkeypatch):
    monkeypatch.setattr(server, "_today_wib", lambda: date(2026, 8, 28))
    server.add_expense("02 Feb 2026", "Makan", "Food", 25000)
    server.add_expense("27 Feb 2026", "Bensin", "Bensin", 35000)
    server.add_expense("01 Mar 2026", "Tidak dihitung", "Food", 50000)

    result = server.get_spending_summary("month", month=2, year=2026)

    assert "Total pengeluaran Februari 2026 (01 Feb 2026–28 Feb 2026): Rp60,000" in result
    assert "Jumlah transaksi: 2" in result
    assert "Tidak dihitung" not in result


def test_compare_monthly_spending(monkeypatch):
    monkeypatch.setattr(server, "_today_wib", lambda: date(2026, 8, 28))
    server.add_expense("02 Jan 2026", "Makan", "Food", 20000)
    server.add_expense("15 Feb 2026", "Makan", "Food", 30000)
    server.add_expense("18 Feb 2026", "Bensin", "Bensin", 35000)

    result = server.compare_monthly_spending(2, 1, 2026)

    assert "Perbandingan Februari 2026 vs Januari 2026" in result
    assert "- Februari 2026: Rp65,000 (2 transaksi)" in result
    assert "- Januari 2026: Rp20,000 (1 transaksi)" in result
    assert "Selisih: naik Rp45,000" in result
    assert "Food: Rp30,000 vs Rp20,000 (naik Rp10,000)" in result


def test_category_budget_reads_allocation_and_realization_from_report(monkeypatch):
    monkeypatch.setattr(server, "_today_wib", lambda: date(2026, 8, 7))
    report = FakeSpreadsheet([
        ["Expenses List", "", "Allocation 💰", "", "Realization 💸"],
        ["Food", "", "Rp100,000", "", "Rp80,000"],
        ["Bensin", "", "Rp250,000", "", "Rp0"],
        ["BPJS", "", "", "", "Rp0"],
    ])
    server._spreadsheet = report
    result = server.add_expense("07 Aug 2026", "Makan", "Food", 1000)

    assert "hampir habis: Rp80,000 dari Rp100,000" in result
    assert "Food: Rp80,000 / Rp100,000" in server.get_category_budgets()
    assert "Bensin: Rp0 / Rp250,000" in server.get_category_budgets()
    assert "BPJS" not in server.get_category_budgets()
    assert report.requested_ranges == [server.BUDGET_PERIOD_RANGE, server.BUDGET_TABLE_RANGE] * 4

    report.values[1][4] = "Rp101,000"
    assert "terlewati: Rp101,000 dari Rp100,000" in server.update_expense("070826-01", amount=2000)


def test_budget_warning_skips_a_different_report_month(monkeypatch):
    monkeypatch.setattr(server, "_today_wib", lambda: date(2026, 8, 7))
    report = FakeSpreadsheet([
        ["Expenses List", "", "Allocation", "", "Realization"],
        ["Food", "", "Rp100,000", "", "Rp150,000"],
    ], period=[["2026"], ["July"]])
    server._spreadsheet = report

    result = server.add_expense("07 Aug 2026", "Makan", "Food", 1000)

    assert "periode Report berbeda" in result
    assert server.BUDGET_TABLE_RANGE not in report.requested_ranges


def test_budget_period_accepts_month_name_from_dropdown():
    server._spreadsheet = FakeSpreadsheet([], period=[["2026"], ["September"]])
    assert server._budget_period() == (2026, 9)


def test_spending_date_range_inclusive_and_validated():
    server.add_expense("01 Aug 2026", "Awal", "Food", 10000)
    server.add_expense("15 Aug 2026", "Akhir", "Bensin", 20000)
    server.add_expense("16 Aug 2026", "Luar", "Food", 30000)

    result = server.get_spending_date_range("2026-08-01", "2026-08-15")
    assert "Rp30,000" in result
    assert "Jumlah transaksi: 2" in result
    assert "Food: Rp10,000" in result
    assert "Bensin: Rp20,000" in result
    assert "Tanggal awal" in server.get_spending_date_range("2026-08-16", "2026-08-01")
    assert "YYYY-MM-DD" in server.get_spending_date_range("01/08/2026", "2026-08-15")
