"""Build the stage 2 results table from the saved runs, so no number in the README is typed by hand.

    python evals/make_table.py            # print the table
    python evals/make_table.py --write    # also replace the block in README.md between the markers

Runs are grouped by model and agent configuration. Where a group has several runs, the worst
case is shown for wrongly-dismissed (the number that must be zero) and the range for the rest.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = "<!-- results:start -->", "<!-- results:end -->"


def _span(values: list[int]) -> str:
    return str(values[0]) if min(values) == max(values) else f"{min(values)} to {max(values)}"


def _reviewer(c: dict) -> str:
    if not c["verify"]:
        return "no second reviewer"
    who = c.get("reviewer", "same model")
    return "second reviewer" if who == "same model" else f"second reviewer `{who}`"


def build_table(runs_dir: Path) -> str:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for path in sorted(runs_dir.glob("*.json")):
        run = json.loads(path.read_text())
        if not isinstance(run, dict) or "score" not in run:
            continue                      # not a run file in the current format
        c = run.get("config") or {}
        label = (f"{c['agent']}, demo set {c.get('dataset', '1')}, {c['runs']} run(s) to clear, "
                 f"{_reviewer(c)}") if c else "not recorded"
        groups[(run.get("model", "?"), label)].append(run["score"])
    if not groups:
        return "_No runs saved yet. Run `python evals/run_agent_eval.py`._"

    rows = ["| Model | Agent configuration | Eval runs | Real problems wrongly dismissed (worst run) "
            "| Decoys cleared | Sent to a lawyer |", "|---|---|---|---|---|---|"]
    for (model, label), scores in sorted(groups.items()):
        real, decoys = scores[0]["real"], scores[0]["decoys"]
        worst = max(len(s["wrongly_dismissed"]) for s in scores)
        cleared = _span([len(s["decoys_cleared"]) for s in scores])
        human = _span([s["sent_to_human"] for s in scores])
        rows.append(f"| `{model}` | {label} | {len(scores)} | {worst} of {real} | {cleared} of {decoys} | {human} |")
    return "\n".join(rows)


if __name__ == "__main__":
    table = build_table(ROOT / "evals" / "runs")
    print(table)
    if "--write" in sys.argv:
        readme = ROOT / "README.md"
        text = readme.read_text()
        if START not in text or END not in text:
            sys.exit("README.md is missing the results markers")
        head, rest = text.split(START, 1)
        readme.write_text(head + START + "\n" + table + "\n" + END + rest.split(END, 1)[1])
        print("\nREADME.md updated")
