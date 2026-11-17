"""One command to check that a change has not broken anything. Needs no model.

    python verify.py

Run it before every commit. If it prints PASS, the tests pass, the demo matter still raises
exactly the labelled findings, and the clean control file still raises nothing.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("regenerate the demo matter", [sys.executable, "make_demo.py"]),
    ("unit tests", [sys.executable, "-m", "unittest", "discover", "tests"]),
    ("stage 1 eval against ground truth", [sys.executable, "evals/run_eval.py"]),
    ("reports build", [sys.executable, "-m", "reconciler", "analyze", "demo_matter", "--out", "out"]),
]

for name, cmd in STEPS:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print(f"{'ok  ' if result.returncode == 0 else 'FAIL'}  {name}")
    if result.returncode != 0:
        print(result.stdout[-3000:], result.stderr[-3000:], sep="\n")
        sys.exit(f"\nFAIL at: {name}")
print("\nPASS")
