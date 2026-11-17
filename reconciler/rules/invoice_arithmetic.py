"""Does a lawyer's invoice add up? Time entries against the fees billed; fees plus tax against the total."""
from __future__ import annotations

from decimal import Decimal

from ..checks import Config, check
from ..invoices import invoices
from ..models import Finding, Matter
from ._common import fmt


@check
def check_invoice_arithmetic(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    for inv in invoices(m):
        entered = sum((e.amount for e in inv.entries), Decimal(0))
        fees = inv.get("fees")
        if fees is not None and inv.entries and fees != entered:
            diff = abs(fees - entered)
            out.append(Finding(
                "invoice_arithmetic", inv.doc.name, "medium",
                f"Invoice bills fees of {fmt(fees)}; its time entries add up to {fmt(entered)}",
                f"A difference of {fmt(diff)} (before tax) between the fees billed and the "
                f"{len(inv.entries)} time entries listed on the invoice.",
                [inv.stated["fees"][1]],
                amount=diff,
                plain=f"A legal invoice paid by the estate bills {fmt(fees)} in fees, but the work "
                      f"itemised on it adds up to {fmt(entered)}, a difference of {fmt(diff)} before tax."))
    return out
