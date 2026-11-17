"""python -m unittest discover tests"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_eval import score  # noqa: E402
from make_demo import build  # noqa: E402
from reconciler.checks import run_all  # noqa: E402
from reconciler.ingest import load_matter  # noqa: E402
from reconciler.retrieval import ask  # noqa: E402


class SeededMatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        build(cls.tmp.name)
        cls.matter = load_matter(cls.tmp.name)
        cls.findings = run_all(cls.matter)

    def test_raises_every_planted_item_and_nothing_else(self):
        r = score(Path(self.tmp.name))
        self.assertEqual(r["missed"], [])
        self.assertEqual(r["unexpected"], [])

    def test_every_finding_cites_a_real_location(self):
        for f in self.findings:
            self.assertTrue(f.evidence, f.title)
            for ev in f.evidence:
                self.assertTrue((Path(self.tmp.name) / ev.doc).exists(), ev.doc)

    def test_retrieval_surfaces_the_missing_tax_documents(self):
        hits = ask(self.matter, self.findings, "Were the T3 trust returns ever provided?")["passages"]
        self.assertTrue(any("T3" in c.text for c in hits[:3]))


class CleanMatter(unittest.TestCase):
    def test_consistent_file_raises_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, seeded=False, decoys=False)
            self.assertEqual([f.title for f in run_all(load_matter(tmp))], [])

    def test_decoys_alone_raise_only_decoys(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, seeded=False, decoys=True)
            keys = {(f.type, f.key) for f in run_all(load_matter(tmp))}
            self.assertEqual(keys, {
                ("amount_mismatch", "D-11"), ("undisclosed_transaction", "2023-08-28:1800.00"),
                ("undisclosed_transaction", "2023-09-05:1250.00"),
                ("undisclosed_transaction", "2023-09-07:1250.00"), ("missing_document", "inventory"),
                ("duplicate_time_entry", "2023-07-11:JW:450.00")})


if __name__ == "__main__":
    unittest.main()
