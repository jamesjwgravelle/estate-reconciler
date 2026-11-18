"""Tests for the dollar totals, the balance bridge, the catalog and the written reports."""
import csv
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_eval import load_truth  # noqa: E402
from make_demo import build  # noqa: E402
from reconciler.agent import Investigation  # noqa: E402
from reconciler.catalog import CATALOG  # noqa: E402
from reconciler.checks import run_all  # noqa: E402
from reconciler.ingest import load_matter  # noqa: E402
from reconciler.models import Evidence  # noqa: E402
from reconciler.report import load_investigations, write_all, write_json  # noqa: E402
from reconciler.summary import balance_bridge, totals  # noqa: E402

# The planted, counted, real amounts other than compensation (which is computed from a guideline):
# funeral 2,000 + roof 8,450 + e-transfer 5,000 + sale figure 13,500 + library gift 10,000 + penalty 350
# + legal fees: invoice shortfall 450 + duplicate entry 225 + personal advice 900
# + tax payment on a reassessment with no notice 1,480. (Agent fees overlap with compensation: not added.)
FIXED_REAL = Decimal("42355.00")
DECOYS = Decimal("6550.00")   # 1,800 + 1,800 + 1,250 + 1,250 + credited duplicate entry 450


class Reports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        build(cls.tmp.name)
        cls.matter = load_matter(cls.tmp.name)
        cls.findings = run_all(cls.matter)
        truth = load_truth()
        cls.comp = next(f for f in cls.findings if f.type == "compensation_review").amount
        # a perfect investigation: every decoy explained, every real problem stands
        cls.invs = [Investigation(f.type, f.key, "explained" if truth[(f.type, f.key)] == "decoy" else "stands",
                                  "because", [Evidence("bank_statement.csv", "line 10", "x")])
                    for f in cls.findings]

    def test_every_type_raised_is_in_the_catalog(self):
        self.assertEqual({f.type for f in self.findings} - set(CATALOG), set())

    def test_every_finding_has_a_plain_sentence(self):
        self.assertEqual([f.title for f in self.findings if not f.plain], [])

    def test_total_before_investigation_includes_the_decoys(self):
        t = totals(self.findings)
        self.assertFalse(t["investigated"])
        self.assertEqual(t["amount_in_question"], FIXED_REAL + self.comp + DECOYS)

    def test_total_after_investigation_leaves_out_explained_items(self):
        t = totals(self.findings, self.invs)
        self.assertEqual(t["amount_in_question"], FIXED_REAL + self.comp)
        self.assertEqual(t["by_status"]["explained"]["count"], 6)
        self.assertEqual(t["open_count"], 21)

    def test_symptoms_are_never_added_to_the_total(self):
        """The $5,000 total error and the balance gap overlap with the items behind them."""
        without = [f for f in self.findings if f.type not in ("arithmetic_error", "balance_mismatch", "date_mismatch")]
        self.assertEqual(totals(self.findings)["amount_in_question"], totals(without)["amount_in_question"])

    def test_reprint_date_is_never_read_as_the_issue_date(self):
        notice = next(d for d in self.matter.texts if d.doc_type == "notice_of_assessment")
        self.assertEqual((str(notice.date), str(notice.reprinted)), ("2024-12-17", "2025-07-02"))
        timeline = next(f for f in self.findings if f.type == "timeline_contradiction")
        self.assertEqual(len([e for e in timeline.evidence if e.doc.startswith("correspondence/")]), 2)
        self.assertIn("reprinted", timeline.detail)

    def test_reassessment_payment_with_its_notice_is_not_raised(self):
        flagged = {f.key for f in self.findings if f.type == "unsupported_tax_payment"}
        self.assertEqual(flagged, {"D-17"})       # D-18 has its notice in the file

    def test_agent_fees_are_shown_but_not_added_twice(self):
        offset = next(f for f in self.findings if f.type == "agent_fee_offset")
        self.assertEqual(offset.amount, Decimal("7200.00"))
        without = [f for f in self.findings if f.type != "agent_fee_offset"]
        self.assertEqual(totals(self.findings)["amount_in_question"], totals(without)["amount_in_question"])

    def test_balance_bridge_traces_the_whole_gap(self):
        b = balance_bridge(self.matter, self.findings)
        self.assertEqual(b["residual"], Decimal("0.00"))
        self.assertNotEqual(b["gap"], Decimal(0))

    def test_balance_bridge_shows_a_residual_when_an_item_is_unidentified(self):
        fewer = [f for f in self.findings if f.type != "undisclosed_transaction" or f.key != "2023-10-20:5000.00"]
        self.assertEqual(balance_bridge(self.matter, fewer)["residual"], Decimal("-5000.00"))

    def test_clean_file_has_no_gap_and_nothing_in_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, seeded=False, decoys=False)
            m = load_matter(tmp)
            self.assertEqual(totals(run_all(m))["amount_in_question"], Decimal(0))
            self.assertEqual(balance_bridge(m, [])["residual"], Decimal("0.00"))

    def test_reports_are_written_and_agree_with_each_other(self):
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            write_json(self.invs, out / "investigations.json")
            invs = load_investigations(out / "investigations.json")      # round trip
            write_all(self.matter, self.findings, invs, out, "Estate of M. Hartwell")
            lawyer = (out / "report_lawyer.html").read_text()
            client = (out / "report_client.html").read_text()
            total = f"${FIXED_REAL + self.comp:,.2f}"
            self.assertIn(total, lawyer)
            self.assertIn(total, client)
            self.assertIn("Draft for your lawyer to review", client)
            self.assertNotIn("row D-", client)                # no citations or entry ids in the client summary
            self.assertIn("Unexplained residual", lawyer)
            rows = list(csv.DictReader((out / "schedule.csv").open()))
            self.assertEqual(len(rows), len(self.findings))
            added = sum(Decimal(r["amount"]) for r in rows if r["added_to_total"] == "yes")
            self.assertEqual(added, FIXED_REAL + self.comp)
            self.assertNotIn("D-11", (out / "draft_request_letter.md").read_text())


if __name__ == "__main__":
    unittest.main()
