"""Forms whose own dates disagree: dated on one day, signed months later.

Some forms carry a printed date from when they were prepared and a separate signature date.
A long gap matters when the timing of the filing is in question, because the printed date can
make a late filing look prompt."""
from __future__ import annotations

import re

from ..checks import Config, check
from ..extract import DOC_TYPES
from ..ingest import ISO_DATE, parse_date
from ..models import Evidence, Finding, Matter

SIGNED = re.compile(r"^\s*(signed|date signed|submitted)\b", re.I)


@check
def check_form_dates(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    for d in m.texts:
        if not d.date or not d.doc_type:
            continue
        for i, line in enumerate(d.lines[:30], start=1):
            hit = ISO_DATE.search(line)
            if not (SIGNED.search(line) and hit):
                continue
            signed = parse_date(hit.group(1))
            gap = (signed - d.date).days
            if gap > cfg.form_signature_gap_days:
                label = DOC_TYPES[d.doc_type][0]
                out.append(Finding(
                    "document_date_conflict", d.doc_type, "medium",
                    f"The {label} is dated {d.date} but was signed on {signed}",
                    f"The form's own date is {gap} days earlier than its signature date. Which date is "
                    "used affects any account of when the step was taken.",
                    [Evidence(d.name, "header", f"dated {d.date}"), Evidence(d.name, f"line {i}", line.strip())],
                    plain=f"The {label} carries a date of {d.date}, but it was signed on {signed}, "
                          f"{gap} days later. The earlier date could make the step look as if it was "
                          "taken sooner than it was."))
                break
    return out
