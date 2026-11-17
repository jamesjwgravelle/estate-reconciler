"""TEMPLATE. Copy this file to a new name without the leading underscore, then edit.

Checklist (the tests enforce most of it):
  1. One function, decorated with @check, taking (m: Matter, cfg: Config).
  2. Return a list of Finding. Return [] when there is nothing to report.
  3. Every Finding needs at least one Evidence that points at a real file and location.
  4. Do all arithmetic here in code, with Decimal. Never ask a model to add or compare.
  5. Add the new type to reconciler/catalog.py.
  6. Plant one example in make_demo.py (only when seeded=True) and label it in
     evals/ground_truth.json. The clean control file must still raise nothing.
  7. Run:  python verify.py
"""
from __future__ import annotations

from ..checks import Config, check
from ..models import Finding, Matter
from ._common import fmt


@check
def my_new_check(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    for t in m.accounts:
        if False:  # replace with the condition that makes this entry worth a question
            out.append(Finding(
                type="my_new_type",              # must exist in catalog.CATALOG
                key=t.id,                        # stable, unique within the type
                severity="medium",               # high | medium | low
                title=f"Short statement of the discrepancy ({fmt(t.amount)})",
                detail="What two sources say and where they differ. No conclusions about conduct.",
                evidence=[t.cite()],
                amount=t.amount,                 # dollars in question, or leave out
                plain="One or two sentences a client could read."))
    return out
