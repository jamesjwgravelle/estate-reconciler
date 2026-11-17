"""Executor compensation against a configurable starting-point guideline."""
from __future__ import annotations

from decimal import Decimal

from ..checks import Config, check
from ..models import Finding, Matter
from ._common import fmt


@check
def check_compensation(m: Matter, cfg: Config) -> list[Finding]:
    comp = [t for t in m.accounts if t.direction == "out" and "compensation" in t.description.lower()]
    if not comp:
        return []
    claimed = sum((t.amount for t in comp), Decimal(0))
    receipts = sum((t.amount for t in m.accounts if t.direction == "in"), Decimal(0))
    disb = sum((t.amount for t in m.accounts if t.direction == "out" and t not in comp), Decimal(0))
    guide = (receipts * cfg.comp_rate_receipts + disb * cfg.comp_rate_disbursements).quantize(Decimal("0.01"))
    if claimed <= guide:
        return []
    return [Finding(
        "compensation_review", comp[0].id, "medium",
        f"Executor compensation of {fmt(claimed)} exceeds the configured guideline of {fmt(guide)}",
        f"Guideline used: {cfg.comp_rate_receipts:.1%} of receipts ({fmt(receipts)}) plus "
        f"{cfg.comp_rate_disbursements:.1%} of other disbursements ({fmt(disb)}). This is a "
        "starting point for review, not a cap; courts adjust for the work actually done.",
        [t.cite() for t in comp],
        amount=claimed - guide,
        plain=f"The executor has taken {fmt(claimed)} in compensation. A common starting point for an "
              f"estate of this size is about {fmt(guide)}, which is {fmt(claimed - guide)} less. "
              "Whether the higher figure is justified depends on the work done.")]
