"""The accounts' own arithmetic: do the totals add up, and does the balance match the bank?"""
from __future__ import annotations

from decimal import Decimal

from ..checks import Config, check
from ..models import Evidence, Finding, Matter
from ._common import fmt, small_bank_items


@check
def check_arithmetic(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    sums = {
        "total_receipts": sum((t.amount for t in m.accounts if t.direction == "in"), Decimal(0)),
        "total_disbursements": sum((t.amount for t in m.accounts if t.direction == "out"), Decimal(0)),
    }
    for key, computed in sums.items():
        if key in m.summary:
            stated, ev = m.summary[key]
            if stated != computed:
                name = key.replace("_", " ")
                # Overstated disbursements (or understated receipts) lower the stated balance.
                effect = stated - computed if key == "total_disbursements" else computed - stated
                out.append(Finding(
                    "arithmetic_error", key, "high",
                    f"Stated {name} is off by {fmt(abs(stated - computed))}",
                    f"The summary states {fmt(stated)}; the itemised entries add up to {fmt(computed)}.",
                    [ev],
                    amount=abs(stated - computed), balance_effect=effect,
                    plain=f"The accounts give {fmt(stated)} as the {name}, but the items listed "
                          f"add up to {fmt(computed)}."))

    if "balance_on_hand" in m.summary and m.bank_closing is not None:
        stated, ev = m.summary["balance_on_hand"]
        # Small bank items we chose not to flag (e.g. monthly fees) legitimately explain a gap.
        small = small_bank_items(m, cfg.materiality)
        expected = m.bank_closing + small
        if abs(stated - expected) > Decimal("0.01"):
            out.append(Finding(
                "balance_mismatch", "balance_on_hand", "high",
                f"Stated balance on hand differs from the bank balance by {fmt(abs(stated - expected))}",
                f"The summary states {fmt(stated)}; the bank record closes at {fmt(m.bank_closing)} "
                f"(with {fmt(small)} of sub-materiality bank items allowed for).",
                [ev, Evidence(m.bank_doc or "bank record", "last line", f"closing balance {fmt(m.bank_closing)}")],
                amount=abs(stated - expected),
                plain=f"The accounts say {fmt(stated)} should be on hand. The bank balance is "
                      f"{fmt(m.bank_closing)}, a difference of {fmt(abs(stated - expected))} after small fees."))
    return out
