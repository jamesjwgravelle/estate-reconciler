"""Payments to the tax authority on a reassessment, against the notices actually produced."""
from __future__ import annotations

import re

from ..checks import Config, check
from ..models import Finding, Matter
from ._common import fmt

REASSESS = re.compile(r"reassess|\bNORA\b", re.I)
YEAR = re.compile(r"\b(20\d\d)\b")


@check
def check_tax_payments(m: Matter, cfg: Config) -> list[Finding]:
    notices = [d for d in m.texts if d.doc_type == "notice_of_reassessment"]
    out: list[Finding] = []
    for t in m.accounts:
        if t.direction != "out" or not REASSESS.search(t.description):
            continue
        year = YEAR.search(t.description)
        amount_text = f"{t.amount:,.2f}"
        supported = any(amount_text in "\n".join(d.lines)
                        and (not year or year.group(1) in "\n".join(d.lines)) for d in notices)
        if not supported:
            out.append(Finding(
                "unsupported_tax_payment", t.id, "medium",
                f"Tax payment of {fmt(t.amount)} on a reassessment, with no matching notice produced",
                "The accounts record a payment on a reassessment, but no Notice of Reassessment for that "
                "amount" + (f" and tax year ({year.group(1)})" if year else "") + " is in the production.",
                [t.cite()],
                amount=t.amount,
                plain=f"The estate paid {fmt(t.amount)} to the tax authority for a reassessment "
                      f"(\"{t.description}\"). We have not been given the notice that says this amount was owed."))
    return out
