"""Time between the final assessment arriving and the clearance certificate being applied for.

An executor usually cannot make a final distribution until the clearance certificate arrives,
and cannot apply for it until the final assessment has been issued. A long gap between the two
holds up the estate and is worth asking about."""
from __future__ import annotations

import re

from ..checks import Config, check
from ..ingest import ISO_DATE, parse_date
from ..models import Evidence, Finding, Matter

SIGNED = re.compile(r"^\s*(signed|date signed|submitted)\b", re.I)


@check
def check_clearance_delay(m: Matter, cfg: Config) -> list[Finding]:
    notices = [d for d in m.texts if d.doc_type == "notice_of_assessment" and d.date]
    apps = [d for d in m.texts if d.doc_type == "clearance_application"]
    if not notices or not apps:
        return []
    notice = max(notices, key=lambda d: d.date)
    out: list[Finding] = []
    for app in apps:
        for i, line in enumerate(app.lines[:30], start=1):
            hit = ISO_DATE.search(line)
            if SIGNED.search(line) and hit:
                applied = parse_date(hit.group(1))
                gap = (applied - notice.date).days
                if gap > cfg.clearance_followup_days:
                    out.append(Finding(
                        "clearance_delay", "clearance_application", "medium",
                        f"Clearance certificate applied for {gap} days after the final assessment",
                        f"The Notice of Assessment is dated {notice.date}; the application was signed on "
                        f"{applied}. The configured threshold is {cfg.clearance_followup_days} days.",
                        [Evidence(notice.name, "header", f"dated {notice.date}"),
                         Evidence(app.name, f"line {i}", line.strip())],
                        plain=f"The tax assessment the executor needed was issued on {notice.date}. The "
                              f"application for the clearance certificate was signed on {applied}, {gap} days "
                              "later. Until the certificate arrives, the estate usually cannot be fully paid out."))
                break
    return out
