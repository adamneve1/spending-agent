import asyncio
from datetime import datetime
from pathlib import Path

import pytest

import report
import scheduler


@pytest.fixture
def report_data(monkeypatch):
    records = {
        (datetime(2026, 9, 11).date(), datetime(2026, 9, 11).date()): [
            {"amount": "100000", "category": "Food"},
            {"amount": "50000", "category": "Bensin"},
        ],
        (datetime(2026, 9, 7).date(), datetime(2026, 9, 11).date()): [
            {"amount": "300000", "category": "Food"},
            {"amount": "200000", "category": "Food"},
            {"amount": "100000", "category": "Bensin"},
        ],
        (datetime(2026, 8, 31).date(), datetime(2026, 9, 6).date()): [
            {"amount": "250000", "category": "Bensin"},
        ],
        (datetime(2026, 9, 1).date(), datetime(2026, 9, 11).date()): [
            {"amount": "500000", "category": "Food"},
            {"amount": "200000", "category": "Bensin"},
        ],
        (datetime(2026, 8, 1).date(), datetime(2026, 8, 31).date()): [
            {"amount": "600000", "category": "Food"},
        ],
    }
    monkeypatch.setattr(report, "_balance", lambda: {"income": 5_747_875, "spending": 2_548_500, "balance": 3_199_375})
    monkeypatch.setattr(report, "_records", lambda start, end: records.get((start, end), []))


def test_daily_report_uses_actual_balance_and_largest_category(report_data):
    message = report.build_daily_financial_report(datetime(2026, 9, 11, 21, 0))

    assert "Pengeluaran hari ini: Rp150,000" in message
    assert "Total Income: Rp5,747,875" in message
    assert "Total Spending: Rp2,548,500" in message
    assert "Sisa Duit: Rp3,199,375" in message
    assert "Food: Rp500,000" in message


def test_weekly_report_calculates_comparison_and_largest_category(report_data):
    message = report.build_weekly_financial_report(datetime(2026, 9, 11, 9, 0))

    assert "Total spending minggu ini: Rp600,000" in message
    assert "Dibanding minggu lalu: naik Rp350,000" in message
    assert "Kategori terbesar: Food: Rp500,000" in message
    assert "Sisa Duit: Rp3,199,375" in message


def test_monthly_report_includes_transactions_and_previous_month_comparison(report_data):
    message = report.build_monthly_financial_report(datetime(2026, 9, 11, 9, 0))

    assert "Total transaksi: 2" in message
    assert "Kategori pengeluaran terbesar: Food: Rp500,000" in message
    assert "Dibanding bulan lalu: naik Rp100,000" in message


def test_report_timezone_defaults_to_asia_jakarta():
    assert report.report_timezone().key == "Asia/Jakarta"


def test_scheduler_config_and_disabled_scheduler_do_not_send(tmp_path):
    config = scheduler.ReportScheduleConfig.from_env(
        {"DAILY_REPORT_ENABLED": "false", "REPORT_TIMEZONE": "Asia/Jakarta", "REPORT_SCHEDULER_STATE_FILE": str(tmp_path / "state.json")},
        allowed_chat_ids=(123,),
    )
    sent = []

    async def send(chat_id, message):
        sent.append((chat_id, message))

    asyncio.run(scheduler.FinancialReportScheduler(config, send).tick(datetime(2026, 9, 11, 21, 0)))
    assert config.timezone == "Asia/Jakarta"
    assert sent == []


def test_scheduler_report_error_isolated_and_does_not_send(tmp_path, monkeypatch):
    config = scheduler.ReportScheduleConfig.from_env(
        {"DAILY_REPORT_ENABLED": "true", "DAILY_REPORT_TIME": "21:00", "REPORT_SCHEDULER_STATE_FILE": str(tmp_path / "state.json")},
        allowed_chat_ids=(123,),
    )
    sent = []

    def fail(_now):
        raise report.ReportDataError("Report tidak tersedia")

    monkeypatch.setitem(scheduler.REPORT_BUILDERS, "daily", fail)

    async def send(chat_id, message):
        sent.append((chat_id, message))

    asyncio.run(scheduler.FinancialReportScheduler(config, send).tick(datetime(2026, 9, 11, 21, 0)))
    assert sent == []


def test_scheduler_persists_sent_report_to_avoid_restart_duplicates(tmp_path, monkeypatch):
    config = scheduler.ReportScheduleConfig.from_env(
        {"DAILY_REPORT_ENABLED": "true", "DAILY_REPORT_TIME": "21:00", "REPORT_SCHEDULER_STATE_FILE": str(tmp_path / "state.json")},
        allowed_chat_ids=(123,),
    )
    sent = []
    monkeypatch.setitem(scheduler.REPORT_BUILDERS, "daily", lambda now: "report aktual")

    async def send(chat_id, message):
        sent.append((chat_id, message))

    now = datetime(2026, 9, 11, 21, 0)
    asyncio.run(scheduler.FinancialReportScheduler(config, send).tick(now))
    asyncio.run(scheduler.FinancialReportScheduler(config, send).tick(now))
    assert sent == [(123, "report aktual")]
