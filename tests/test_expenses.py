import re

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
        self.rows[row - 1][column - 1] = str(value)

    def get_all_values(self):
        return self.rows

    def delete_rows(self, row):
        del self.rows[row - 1]


def setup_function():
    server._sheet = FakeSheet()


def test_add_creates_id_and_get_finds_expense():
    result = server.add_expense("05 Aug 2026", "Makan siang", "Food", 25000)
    transaction_id = re.search(r"EXP-\d{8}-[A-F0-9]{8}", result).group(0)

    assert "Transaction ID" in result
    assert transaction_id in server.get_expense(transaction_id.lower())
    assert "Makan siang" in server.get_expense(transaction_id)


def test_search_update_and_delete_expense():
    result = server.add_expense("05 Aug 2026", "Makan siang", "Food", 25000)
    transaction_id = re.search(r"EXP-\d{8}-[A-F0-9]{8}", result).group(0)

    assert transaction_id in server.search_expenses(category="food")
    assert "Makan malam" in server.update_expense(transaction_id, description="Makan malam", amount=30000)
    assert "Rp30000" in server.get_expense(transaction_id)
    assert "berhasil dihapus" in server.delete_expense(transaction_id)
    assert "tidak ditemukan" in server.get_expense(transaction_id)


def test_update_requires_a_real_change_and_unknown_id_is_safe():
    assert "tidak ditemukan" in server.delete_expense("EXP-UNKNOWN")
    result = server.add_expense("05 Aug 2026", "Kopi", "Food", 10000)
    transaction_id = re.search(r"EXP-\d{8}-[A-F0-9]{8}", result).group(0)
    assert server.update_expense(transaction_id) == "Tidak ada perubahan yang diberikan."
