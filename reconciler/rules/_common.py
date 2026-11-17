"""Small helpers shared by the checks."""
from __future__ import annotations

from decimal import Decimal

from ..extract import tokens
from ..models import Matter, Txn


def fmt(x: Decimal) -> str:
    return f"${x:,.2f}"


def days(a: Txn, b: Txn) -> int:
    return abs((a.date - b.date).days)


def similar(a: str, b: str) -> bool:
    return len(tokens(a) & tokens(b)) >= 1


def small_bank_items(m: Matter, materiality: Decimal) -> Decimal:
    """Net money out through bank items too small to flag (monthly fees and the like)."""
    return sum((b.amount if b.direction == "out" else -b.amount
                for b in m.bank if b.amount < materiality), Decimal(0))
