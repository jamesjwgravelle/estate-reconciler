"""A paid agent (such as a trust company) administering the estate, and full executor compensation.

Where an executor hands the work of administration to an agent paid from the estate, the
estate risks paying twice for the same work. Courts may reduce the executor's compensation by
some or all of the agent's fees. How much is a question of judgment, so the agent never decides
this one; it always goes to a lawyer."""
from __future__ import annotations

import re
from decimal import Decimal

from ..checks import Config, check
from ..extract import statements
from ..models import Finding, Matter
from ._common import fmt

AGENT = re.compile(r"\bagent\b|trust company|management fee|administration fee", re.I)
CLAUSE = re.compile(r"\bemploy\b.*\b(agent|trust company)\b", re.I)


@check
def check_agent_fee_offset(m: Matter, cfg: Config) -> list[Finding]:
    paid_out = [t for t in m.accounts if t.direction == "out"]
    comp = [t for t in paid_out if "compensation" in t.description.lower()]
    agent = [t for t in paid_out if AGENT.search(t.description) and t not in comp]
    if not comp or not agent:
        return []
    fees = sum((t.amount for t in agent), Decimal(0))
    claimed = sum((t.amount for t in comp), Decimal(0))
    clause = [s.cite() for d in m.texts if d.doc_type == "will" for s in statements(d) if CLAUSE.search(s.text)]
    return [Finding(
        "agent_fee_offset", comp[0].id, "medium",
        f"Agent fees of {fmt(fees)} paid as well as executor compensation of {fmt(claimed)}",
        f"{len(agent)} payment(s) to an agent for administering the estate total {fmt(fees)}. The executor "
        f"also claims {fmt(claimed)} in compensation. Whether compensation should be reduced to reflect "
        "work done by the paid agent is a question for counsel."
        + (" The Will permits employing an agent; that permits the expense, it does not settle the offset."
           if clause else ""),
        [t.cite() for t in agent] + [t.cite() for t in comp] + clause,
        amount=min(fees, claimed),
        plain=f"The estate paid an agent {fmt(fees)} to help administer it, and the executor also took "
              f"{fmt(claimed)} in compensation. Where someone else was paid to do part of the executor's "
              "work, a court may reduce the executor's compensation so the estate does not pay twice. "
              "How much, if anything, is a question for your lawyer.")]
