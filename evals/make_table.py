"""Build the README's results tables, so no number in them is typed by hand.

    python evals/make_table.py            # print both tables
    python evals/make_table.py --write    # replace both blocks in README.md between their markers
    python evals/make_table.py --check    # exit 1 if README.md is out of date (verify.py runs this)

Stage 1 is computed fresh: the demo matter is rebuilt in a temporary folder and scored against
evals/ground_truth.json, and the clean control is built and checked. Stage 2 comes from the
saved runs in evals/runs/.

Runs are grouped by model and agent configuration. Where a group has several runs, the worst
case is shown for wrongly-dismissed (the number that must be zero) and the range for the rest.
"""
from __future__ import annotations

import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
START, END = "<!-- results:start -->", "<!-- results:end -->"
S1_START, S1_END = "<!-- stage1:start -->", "<!-- stage1:end -->"


def build_stage1_table() -> str:
    from evals.run_eval import load_truth, score
    from make_demo import DATASET_VERSION, build
    from reconciler.checks import run_all
    from reconciler.ingest import load_matter

    truth = load_truth()
    real = sum(1 for v in truth.values() if v == "real")
    decoys = len(truth) - real
    with tempfile.TemporaryDirectory() as tmp:
        build(tmp)
        r = score(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        build(tmp, seeded=False, decoys=False)
        m = load_matter(tmp)
        clean = len(run_all(m))
        docs = len(m.texts)
    raised_real = round(r["precision"] * r["raised"])
    return "\n".join([
        "| Measure | Result |",
        "|---|---|",
        f"| Labelled items in the demo matter (dataset {DATASET_VERSION}) | {real} real problems, {decoys} decoys |",
        f"| Raises every labelled item, nothing else | {r['expected'] - len(r['missed'])} of {r['expected']}, "
        f"{len(r['unexpected'])} unexpected |",
        f"| Share of raised items that are real problems | {r['precision']:.0%} ({raised_real} of {r['raised']}), by design |",
        f"| Control file with no problems ({docs} documents besides the ledgers) | {clean} findings |",
    ])


def _replace(text: str, start: str, end: str, block: str) -> str:
    if start not in text or end not in text:
        sys.exit(f"README.md is missing the markers {start} ... {end}")
    head, rest = text.split(start, 1)
    return head + start + "\n" + block + "\n" + end + rest.split(end, 1)[1]


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
            "| Decoys cleared | Sent to a lawyer | of which model errors |", "|---|---|---|---|---|---|---|"]
    for (model, label), scores in sorted(groups.items()):
        real, decoys = scores[0]["real"], scores[0]["decoys"]
        worst = max(len(s["wrongly_dismissed"]) for s in scores)
        cleared = _span([len(s["decoys_cleared"]) for s in scores])
        human = _span([s["sent_to_human"] for s in scores])
        errors = _span([s.get("model_errors", 0) for s in scores])
        rows.append(f"| `{model}` | {label} | {len(scores)} | {worst} of {real} | {cleared} of {decoys} | {human} | {errors} |")
    return "\n".join(rows)


if __name__ == "__main__":
    stage1, stage2 = build_stage1_table(), build_table(ROOT / "evals" / "runs")
    print(stage1, stage2, sep="\n\n")
    readme = ROOT / "README.md"
    text = readme.read_text()
    updated = _replace(_replace(text, S1_START, S1_END, stage1), START, END, stage2)
    if "--check" in sys.argv and updated != text:
        sys.exit("\nREADME.md results are out of date: run  python evals/make_table.py --write")
    if "--write" in sys.argv:
        readme.write_text(updated)
        print("\nREADME.md updated" if updated != text else "\nREADME.md already current")
