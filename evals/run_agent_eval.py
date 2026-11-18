"""Stage 2: score the investigator agent. Needs a model (see README).

    python evals/run_agent_eval.py                      # full agent: 3 agreeing runs + second reviewer
    python evals/run_agent_eval.py --runs 1 --no-verify # the bare agent, to measure what the checks add

Each run is saved to evals/runs/<model>_<time>.json. `python evals/make_table.py` turns
that folder into the results table.

Two numbers, in order of importance:

  wrongly dismissed   real problems the agent marked "explained". Must be zero.
  decoys cleared      decoys the agent correctly marked "explained". Higher is better.

"needs_human" is never an error; it is the safe answer. But an agent that sends everything
to a human is useless, so the share sent to review is reported too.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_eval import load_truth  # noqa: E402
from make_demo import DATASET_VERSION  # noqa: E402
from reconciler import llm  # noqa: E402
from reconciler.agent import AGENT_VERSION, Investigation, investigate_all  # noqa: E402
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
        # Timeouts and connection failures: infrastructure, not judgment. Counted separately so a
        # slow machine does not look like a cautious model.
        "model_errors": sum(1 for i in invs if i.note.startswith(("model error", "reviewer error"))),
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
    if r.get("model_errors"):
        print(f"    of which model errors (timeouts etc.): {r['model_errors']}")
    print(f"precision of what remains: {r['precision_after']:.0%}")
    for t, k, note in r["overridden_by_guardrail"]:
        print(f"    guardrail: {t} / {k}: {note}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3, help="agreeing runs needed to clear a finding")
    ap.add_argument("--no-verify", action="store_true", help="skip the second reviewer")
    args = ap.parse_args()
    if not llm.configured():
        sys.exit("set RECONCILER_LLM_BASE_URL and RECONCILER_LLM_MODEL first (see README)")

    model = os.environ["RECONCILER_LLM_MODEL"]
    reviewer = llm.reviewer_client() if not args.no_verify else None
    config = {"agent": AGENT_VERSION, "dataset": DATASET_VERSION, "runs": args.runs, "verify": not args.no_verify,
              "reviewer": reviewer.model if reviewer else "same model"}
    print(f"model: {model}   agent: {config}\n")
    matter = load_matter(ROOT / "demo_matter")
    invs = investigate_all(run_all(matter), matter, llm.Client(), runs=args.runs, verify=not args.no_verify, reviewer=reviewer,
                           progress=lambda f, i: print(f"[{i.verdict:<11}] {f.type} / {f.key}"))
    result = score_investigations(invs, load_truth())

    # One file per run, so a later run never overwrites the evidence for an earlier one.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    runs_dir = ROOT / "evals" / "runs"
    runs_dir.mkdir(exist_ok=True)
    out = runs_dir / f"{re.sub(r'[^A-Za-z0-9.]+', '-', model)}_{stamp}.json"
    out.write_text(json.dumps({"model": model, "run_at": stamp, "config": config, "score": result,
                               "investigations": [i.to_dict() for i in invs]}, indent=2))
    print()
    print_score(result)
    print(f"\nsaved {out.relative_to(ROOT)}")
    sys.exit(1 if result["wrongly_dismissed"] else 0)
