"""Penalties and late charges paid out of the estate."""
from __future__ import annotations

import re

from ..checks import Config, check
from ..models import Finding, Matter
from ._common import fmt

CHARGE = re.compile(r"penalt|late[- ]fil|late fee|late charge|\bnsf\b|overdraft|arrears interest", re.I)


@check
def check_avoidable_costs(m: Matter, cfg: Config) -> list[Finding]:
    return [Finding(
        "avoidable_cost", t.id, "medium",
        f"Estate paid {fmt(t.amount)} described as \"{t.description}\"",
        "A penalty or late charge was paid from estate funds. Whether the estate or the "
        "person responsible for the delay should bear it is a question for counsel.",
        [t.cite()],
        amount=t.amount,
        plain=f"The estate paid {fmt(t.amount)} for \"{t.description}\". Whether the estate "
              "should bear a charge like this is a question for your lawyer.")
        for t in m.accounts if t.direction == "out" and CHARGE.search(t.description)]
