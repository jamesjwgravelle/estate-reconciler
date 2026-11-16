"""Stage 1: score the first-pass checks against the labelled demo matter.

    python evals/run_eval.py

The first pass is meant to over-flag: it should raise every real problem AND every decoy,
because it has no way to tell them apart. So:

  coverage   of everything it should raise (real + decoy), how much it raised
  unexpected findings that are in neither list (must be none)
  precision  of what it raised, the share that is a real problem. This is the number the
             investigator (stage 2, run_agent_eval.py) exists to improve.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reconciler.checks import run_all  # noqa: E402
from reconciler.ingest import load_matter  # noqa: E402

TRUTH = ROOT / "evals" / "ground_truth.json"


def load_truth(path: Path = TRUTH) -> dict[tuple[str, str], str]:
    return {(t["type"], t["key"]): t["label"] for t in json.loads(path.read_text())}


def score(matter_dir: Path, truth_path: Path = TRUTH) -> dict:
    truth = load_truth(truth_path)
    found = {(f.type, f.key) for f in run_all(load_matter(matter_dir))}
    real = {k for k, v in truth.items() if v == "real"}
    return {
        "expected": len(truth), "raised": len(found),
        "coverage": len(found & set(truth)) / len(truth),
        "precision": len(found & real) / len(found) if found else 1.0,
        "missed": sorted(set(truth) - found), "unexpected": sorted(found - set(truth)),
    }


if __name__ == "__main__":
    r = score(ROOT / "demo_matter")
    print(f"expected {r['expected']}  raised {r['raised']}")
    print(f"coverage {r['coverage']:.0%}  first-pass precision {r['precision']:.0%}")
    for label in ("missed", "unexpected"):
        for t, k in r[label]:
            print(f"  {label}: {t} / {k}")
    sys.exit(0 if not r["missed"] and not r["unexpected"] else 1)
