import sys
from pathlib import Path

import pytest

# GitHub Actions may collect tests with only the tests directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Settings


def test_settings_support_a_moved_account_and_sheet_layout(tmp_path):
    credentials = tmp_path / "other-account.json"
    settings = Settings.from_env({
        "SPREADSHEET_ID": "new-spreadsheet",
        "WORKSHEET_NAME": "Expenses",
        "GOOGLE_CREDENTIALS_PATH": str(credentials),
        "EXPENSE_ID_COLUMN": "2",
        "EXPENSE_DATE_COLUMN": "3",
        "EXPENSE_DESCRIPTION_COLUMN": "4",
        "EXPENSE_CATEGORY_COLUMN": "5",
        "EXPENSE_AMOUNT_COLUMN": "6",
        "REPORT_DASHBOARD_RANGE": "Summary!A1:Z50",
        "BUDGET_TABLE_RANGE": "Report!A1:F100",
        "BUDGET_PERIOD_RANGE": "Report!J2:J3",
    })

    assert settings.spreadsheet_id == "new-spreadsheet"
    assert settings.worksheet_name == "Expenses"
    assert settings.google_credentials_path == credentials
    assert settings.expense_category_column == 5
    assert settings.report_dashboard_range == "Summary!A1:Z50"
    assert settings.budget_table_range == "Report!A1:F100"
    assert settings.budget_period_range == "Report!J2:J3"


def test_settings_reject_overlapping_columns():
    with pytest.raises(ValueError, match="tidak boleh sama"):
        Settings.from_env({"EXPENSE_ID_COLUMN": "3"})
