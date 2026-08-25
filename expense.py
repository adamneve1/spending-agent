"""Compatibility module for expense operations.

The executable MCP implementation lives in ``server.py``. Importing this
module has no side effect, so it cannot create a test transaction.
"""

from server import add_expense, delete_expense, get_expense, search_expenses, update_expense

__all__ = [
    "add_expense",
    "delete_expense",
    "get_expense",
    "search_expenses",
    "update_expense",
]
