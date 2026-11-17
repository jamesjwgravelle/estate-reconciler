"""Legal time that appears to be advice to the executor personally, billed to the estate."""
from __future__ import annotations

import re

from ..checks import Config, check
from ..invoices import invoices
from ..models import Finding, Matter
from ._common import fmt

PERSONAL = re.compile(r"\bpersonal(ly)?\b|executor'?s? conduct|\bremoval\b|\bobjections?\b", re.I)


@check
def check_personal_fees(m: Matter, cfg: Config) -> list[Finding]:
    return [Finding(
        "personal_legal_fees", f"{e.date}:{e.timekeeper}:{e.amount:.2f}", "medium",
        f"Time entry of {e.date} ({fmt(e.amount)}) may be advice to the executor personally",
        "The description suggests work for the executor's own benefit, billed on an invoice the "
        "estate paid. Whether the estate should bear it is a question for counsel. Amount is before tax.",
        [e.evidence],
        amount=e.amount,
        plain=f"A legal invoice paid by the estate includes {fmt(e.amount)} for \"{e.description}\". "
              "Whether the estate or the executor should pay for this is a question for your lawyer.")
        for inv in invoices(m) for e in inv.entries if e.amount > 0 and PERSONAL.search(e.description)]
