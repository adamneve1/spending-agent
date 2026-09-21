"""Settings that vary between installations and spreadsheet accounts."""

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    telegram_bot_token: str | None
    allowed_telegram_user_ids: str | None
    gemini_model: str
    spreadsheet_id: str | None
    worksheet_name: str
    google_credentials_path: Path
    expense_id_column: int
    expense_date_column: int
    expense_description_column: int
    expense_category_column: int
    expense_amount_column: int
    expense_first_data_row: int
    report_dashboard_range: str
    budget_table_range: str
    budget_period_range: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        settings = cls(
            gemini_api_key=env.get("GEMINI_API_KEY"),
            telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN"),
            allowed_telegram_user_ids=env.get("ALLOWED_TELEGRAM_USER_IDS"),
            gemini_model=env.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            spreadsheet_id=env.get("SPREADSHEET_ID"),
            worksheet_name=env.get("WORKSHEET_NAME", "Spending"),
            google_credentials_path=Path(env.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")),
            expense_id_column=int(env.get("EXPENSE_ID_COLUMN", "1")),
            expense_date_column=int(env.get("EXPENSE_DATE_COLUMN", "3")),
            expense_description_column=int(env.get("EXPENSE_DESCRIPTION_COLUMN", "4")),
            expense_category_column=int(env.get("EXPENSE_CATEGORY_COLUMN", "6")),
            expense_amount_column=int(env.get("EXPENSE_AMOUNT_COLUMN", "7")),
            expense_first_data_row=int(env.get("EXPENSE_FIRST_DATA_ROW", "2")),
            report_dashboard_range=env.get("REPORT_DASHBOARD_RANGE", "Report!A1:AZ200"),
            budget_table_range=env.get("BUDGET_TABLE_RANGE", "Report!B11:G32"),
            budget_period_range=env.get("BUDGET_PERIOD_RANGE", "Report!K2:K3"),
        )
        columns = (
            settings.expense_id_column,
            settings.expense_date_column,
            settings.expense_description_column,
            settings.expense_category_column,
            settings.expense_amount_column,
        )
        if any(column < 1 for column in columns) or len(set(columns)) != len(columns):
            raise ValueError("Kolom expense harus angka positif dan tidak boleh sama")
        if settings.expense_first_data_row < 2:
            raise ValueError("EXPENSE_FIRST_DATA_ROW minimal 2")
        if not settings.google_credentials_path.is_absolute():
            settings = replace(settings, google_credentials_path=Path(__file__).resolve().parent / settings.google_credentials_path)
        return settings


settings = Settings.from_env()
