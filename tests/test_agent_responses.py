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


def test_agent_combines_multiple_added_expenses_in_one_reply(agent_module):
    results = [
        (
            {"description": "Susu Dancow", "amount": 4000, "category": "Food"},
            "Expense berhasil ditambahkan. Transaction ID: 220926-02 | 22 Sep 2026 | Susu Dancow | Food | Rp4,000\n⚠️ Budget Food terlewati: Rp973,600 dari Rp500,000.",
        ),
        (
            {"description": "Mie Sukses isi 2", "amount": 4000, "category": "Food"},
            "Expense berhasil ditambahkan. Transaction ID: 220926-03 | 22 Sep 2026 | Mie Sukses isi 2 | Food | Rp4,000\n⚠️ Budget Food terlewati: Rp977,600 dari Rp500,000.",
        ),
        (
            {"description": "Telur 5", "amount": 10000, "category": "Food"},
            "Expense berhasil ditambahkan. Transaction ID: 220926-04 | 22 Sep 2026 | Telur 5 | Food | Rp10,000\n⚠️ Budget Food terlewati: Rp987,600 dari Rp500,000.",
        ),
    ]

    reply = agent_module._multiple_add_expenses_reply(results)

    assert "3 pengeluaran sudah dicatat" in reply
    assert "Susu Dancow: Rp4,000 — ID 220926-02" in reply
    assert "Mie Sukses isi 2: Rp4,000 — ID 220926-03" in reply
    assert "Telur 5: Rp10,000 — ID 220926-04" in reply
    assert "Rp987,600 dari Rp500,000" in reply
    assert "Rp973,600 dari Rp500,000" not in reply


def test_agent_extracts_batch_delete_ids(agent_module):
    message = """hapus yang ini:
- susu dancow — ID 220926-05
- mie sukses — ID 220926-06
- telur — ID 220926-07
- duplikat — ID 220926-05
"""

    assert agent_module._delete_request_ids(message) == (
        "220926-05",
        "220926-06",
        "220926-07",
    )
    assert agent_module._delete_confirmation_ids(
        "konfirmasi hapus 220926-05 220926-06 220926-07"
    ) == ("220926-05", "220926-06", "220926-07")
    assert agent_module._delete_request_ids("tolong cek 220926-05") == ()


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
