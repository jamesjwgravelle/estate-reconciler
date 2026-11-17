"""The numbers in the reports: dollar totals and the balance bridge. Plain code, no model.

Two rules keep the headline figure defensible:

  1. Nothing is counted twice. A wrong total and a balance gap are symptoms of the individual
     items, so their amounts are shown but not added (catalog.CATALOG decides, per type).
  2. Anything the investigator found to be explained by the file is left out of the total.
"""
from __future__ import annotations

from decimal import Decimal

from .catalog import CATALOG, info
from .checks import Config
from .models import Finding, Matter
from .rules._common import small_bank_items

ZERO = Decimal(0)
OPEN = ("stands", "needs_human", "not_investigated")


def statuses(findings: list[Finding], investigations: list | None) -> dict[tuple[str, str], str]:
    """Status of each finding: explained | stands | needs_human | not_investigated."""
    verdict = {(i.type, i.key): i.verdict for i in investigations or []}
    return {(f.type, f.key): verdict.get((f.type, f.key), "not_investigated") for f in findings}


def totals(findings: list[Finding], investigations: list | None = None) -> dict:
    status = statuses(findings, investigations)
    counted = lambda f: info(f.type).counted and f.amount is not None  # noqa: E731
    by_status = {s: {"count": 0, "amount": ZERO} for s in (*OPEN, "explained")}
    for f in findings:
        row = by_status[status[(f.type, f.key)]]
        row["count"] += 1
        if counted(f):
            row["amount"] += f.amount

    categories = []
    for cat in dict.fromkeys(t.category for t in CATALOG.values()):       # catalog order, no repeats
        items = [f for f in findings if info(f.type).category == cat and status[(f.type, f.key)] in OPEN]
        if items:
            categories.append({
                "category": cat, "count": len(items),
                "counted": any(info(f.type).counted for f in items),
                "amount": sum((f.amount for f in items if f.amount is not None), ZERO),
                "has_amount": any(f.amount is not None for f in items)})

    return {
        "investigated": bool(investigations),
        "open_count": sum(by_status[s]["count"] for s in OPEN),
        "amount_in_question": sum((by_status[s]["amount"] for s in OPEN), ZERO),
        "by_status": by_status,
        "categories": categories,
    }


def balance_bridge(m: Matter, findings: list[Finding], cfg: Config | None = None) -> dict | None:
    """Show that the individual findings add up to the gap between the stated balance and the bank.

    A residual of zero means every dollar of the gap is traced to a listed item. A residual
    that is not zero means something moved the balance that no check has identified."""
    if "balance_on_hand" not in m.summary or m.bank_closing is None:
        return None
    cfg = cfg or Config()
    stated = m.summary["balance_on_hand"][0]
    small = small_bank_items(m, cfg.materiality)
    gap = m.bank_closing - stated
    lines = [(f, f.balance_effect) for f in findings if f.balance_effect]
    traced = sum((e for _, e in lines), ZERO) - small
    return {"stated": stated, "bank": m.bank_closing, "gap": gap, "lines": lines,
            "small_items": small, "residual": gap - traced}
