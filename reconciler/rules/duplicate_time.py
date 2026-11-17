"""The same time entry appearing twice on a lawyer's invoice."""
from __future__ import annotations

from collections import defaultdict

from ..checks import Config, check
from ..invoices import invoices
from ..models import Finding, Matter
from ._common import fmt


@check
def check_duplicate_time(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    for inv in invoices(m):
        groups = defaultdict(list)
        for e in inv.entries:
            if e.amount > 0:
                groups[(e.date, e.timekeeper, e.description.lower(), e.hours)].append(e)
        for same in groups.values():
            if len(same) < 2:
                continue
            e, extra = same[0], sum(x.amount for x in same[1:])
            out.append(Finding(
                "duplicate_time_entry", f"{e.date}:{e.timekeeper}:{e.amount:.2f}", "medium",
                f"Time entry of {e.date} ({fmt(e.amount)}) appears {len(same)} times on the invoice",
                f"The same date, timekeeper, description and hours are billed {len(same)} times. "
                f"The repeat amounts to {fmt(extra)} before tax.",
                [x.evidence for x in same],
                amount=extra,
                plain=f"A legal invoice paid by the estate lists the same work twice on {e.date} "
                      f"(\"{e.description}\"). The repeat is {fmt(extra)} before tax."))
    return out
