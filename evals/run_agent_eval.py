"""Stage 2: score the investigator agent. Needs a model (see README).

    python evals/run_agent_eval.py            # writes evals/last_agent_run.json

Two numbers, in order of importance:

  wrongly dismissed   real problems the agent marked "explained". Must be zero.
  decoys cleared      decoys the agent correctly marked "explained". Higher is better.

"needs_human" is never an error; it is the safe answer. But an agent that sends everything
to a human is useless, so the share sent to review is reported too.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_eval import load_truth  # noqa: E402
from reconciler import llm  # noqa: E402
from reconciler.agent import Investigation, investigate_all  # noqa: E402
from reconciler.checks import run_all  # noqa: E402
from reconciler.ingest import load_matter  # noqa: E402


def score_investigations(invs: list[Investigation], truth: dict[tuple[str, str], str]) -> dict:
    real = [i for i in invs if truth.get((i.type, i.key)) == "real"]
    decoy = [i for i in invs if truth.get((i.type, i.key)) == "decoy"]
    dismissed = [(i.type, i.key) for i in real if i.verdict == "explained"]
    cleared = [(i.type, i.key) for i in decoy if i.verdict == "explained"]
    kept = [i for i in invs if i.verdict != "explained"]
    return {
        "real": len(real), "decoys": len(decoy),
        "wrongly_dismissed": dismissed,
        "decoys_cleared": cleared,
        "decoys_not_cleared": [(i.type, i.key, i.verdict) for i in decoy if i.verdict != "explained"],
        "sent_to_human": sum(i.verdict == "needs_human" for i in invs),
        "overridden_by_guardrail": [(i.type, i.key, i.note) for i in invs if i.note],
        "precision_after": (sum(truth.get((i.type, i.key)) == "real" for i in kept) / len(kept)) if kept else 1.0,
    }


def print_score(r: dict) -> None:
    print(f"wrongly dismissed: {len(r['wrongly_dismissed'])} of {r['real']} real problems")
    for t, k in r["wrongly_dismissed"]:
        print(f"    {t} / {k}")
    print(f"decoys cleared:    {len(r['decoys_cleared'])} of {r['decoys']}")
    for t, k, v in r["decoys_not_cleared"]:
        print(f"    not cleared: {t} / {k} ({v})")
    print(f"sent to a human:   {r['sent_to_human']}")
    print(f"precision of what remains: {r['precision_after']:.0%}")
    for t, k, note in r["overridden_by_guardrail"]:
        print(f"    guardrail: {t} / {k}: {note}")


if __name__ == "__main__":
    if not llm.configured():
        sys.exit("set RECONCILER_LLM_BASE_URL and RECONCILER_LLM_MODEL first (see README)")
    matter = load_matter(ROOT / "demo_matter")
    invs = investigate_all(run_all(matter), matter, llm.Client(),
                           progress=lambda f, i: print(f"[{i.verdict:<11}] {f.type} / {f.key}"))
    (ROOT / "evals" / "last_agent_run.json").write_text(json.dumps([i.to_dict() for i in invs], indent=2))
    print()
    result = score_investigations(invs, load_truth())
    print_score(result)
    sys.exit(1 if result["wrongly_dismissed"] else 0)
