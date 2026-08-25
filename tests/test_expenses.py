import re
import sys
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
