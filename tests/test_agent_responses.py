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
