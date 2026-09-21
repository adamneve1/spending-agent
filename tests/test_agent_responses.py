import importlib
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def agent_module():
    os.environ.setdefault("GEMINI_API_KEY", "test-key")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
    os.environ.setdefault("ALLOWED_TELEGRAM_USER_IDS", "1")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    return importlib.import_module("agent")


def test_agent_replies_with_exact_mcp_transaction_id(agent_module):
    mcp_result = "Expense berhasil ditambahkan. Transaction ID: 110926-04 | 11 Sep 2026"

    reply = agent_module._add_expense_reply(mcp_result)

    assert reply.endswith("Transaction ID: 110926-04")
    assert "55959960" not in reply


def test_agent_never_invents_a_missing_or_invalid_transaction_id(agent_module):
    missing = agent_module._add_expense_reply("Expense berhasil ditambahkan. | 11 Sep 2026")
    invalid = agent_module._add_expense_reply(
        "Expense berhasil ditambahkan. Transaction ID: 55959960"
    )

    assert "Transaction ID gagal diperoleh" in missing
    assert "Transaction ID gagal diperoleh" in invalid
    assert "110926-01" not in missing + invalid


def test_agent_shows_budget_warning_after_add(agent_module):
    result = "Expense berhasil ditambahkan. Transaction ID: 110926-04 | 11 Sep 2026\n⚠️ Budget Food hampir habis: Rp80,000 dari Rp100,000 (80%)."
    assert "Budget Food hampir habis" in agent_module._add_expense_reply(result)


@pytest.mark.parametrize(
    ("question", "expected", "excluded"),
    [
        ("saldo gue berapa?", "Saldo lu sekarang Rp3,199,375, Bos.", "Total Income"),
        ("sisa duit gue berapa?", "Saldo lu sekarang Rp3,199,375, Bos.", "Total Spending"),
        ("total spending gue berapa?", "Total spending lu Rp2,548,500, Bos.", "Total Income"),
        ("income gue berapa?", "Total income lu Rp5,747,875, Bos.", "Sisa Duit"),
    ],
)
def test_agent_selects_only_the_requested_balance_figure(agent_module, question, expected, excluded):
    result = "Total Income: Rp5,747,875\nTotal Spending: Rp2,548,500\nSisa Duit: Rp3,199,375"

    reply = agent_module._financial_balance_reply(question, result)

    assert reply == expected
    assert excluded not in reply


def test_agent_returns_all_mcp_figures_for_financial_overview(agent_module):
    result = "Total Income: Rp5,747,875\nTotal Spending: Rp2,548,500\nSisa Duit: Rp3,199,375"

    reply = agent_module._financial_balance_reply("cek keuangan gue", result)

    assert "Total Income: Rp5,747,875" in reply
    assert "Total Spending: Rp2,548,500" in reply
    assert "Sisa Duit: Rp3,199,375" in reply
