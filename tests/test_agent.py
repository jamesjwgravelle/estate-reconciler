"""Tests for the investigator's plumbing and guardrails, using a scripted stand-in for the model.

These prove that the loop, the tools and the overrides behave. They say nothing about how
well a real model investigates; evals/run_agent_eval.py measures that.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_agent_eval import score_investigations  # noqa: E402
from evals.run_eval import load_truth  # noqa: E402
from make_demo import build  # noqa: E402
from reconciler.agent import investigate, investigate_all  # noqa: E402
from reconciler.checks import run_all  # noqa: E402
from reconciler.ingest import load_matter  # noqa: E402
from reconciler.letter import draft_request  # noqa: E402
from reconciler.tools import Toolbox  # noqa: E402


def call(name, **args):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}]}


class Scripted:
    """Plays back a fixed list of assistant messages; records what it was sent."""
    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []

    def complete(self, messages, tools=None):
        self.seen.append(list(messages))
        if not self.turns:
            return {"role": "assistant", "content": "I am not sure."}
        turn = self.turns.pop(0)
        return turn(messages) if callable(turn) else turn


BANK_14 = "bank_statement.csv :: line 10"
BANK_28 = "bank_statement.csv :: line 11"


class AgentGuardrails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        build(cls.tmp.name)
        cls.matter = load_matter(cls.tmp.name)
        cls.findings = run_all(cls.matter)
        cls.by_key = {(f.type, f.key): f for f in cls.findings}
        cls.split = cls.by_key[("amount_mismatch", "D-11")]

    def test_tools_can_reach_every_decoy_explanation(self):
        """The eval is only fair if the explanations are findable with the tools given."""
        box = Toolbox(self.matter)
        cheques = box.call("find_transactions", {"source": "bank", "text": "brightway"})
        self.assertEqual([c["ref"] for c in cheques], [BANK_14, BANK_28])
        self.assertEqual(box.call("add_amounts", {"amounts": [1800, 1800]}), {"total": "3600.00"})
        wires = box.call("find_transactions", {"source": "bank", "text": "77812"})
        self.assertEqual({w["direction"] for w in wires}, {"money in", "money out"})
        hits = box.call("search_documents", {"query": "assets of the estate owned at death"})
        self.assertTrue(any(h["ref"].startswith("schedule_a_assets.txt") for h in hits))

    def test_explained_with_new_valid_citations_is_accepted(self):
        client = Scripted(
            call("find_transactions", source="bank", text="brightway"),
            call("add_amounts", amounts=[1800, 1800]),
            call("submit_verdict", verdict="explained", explanation="Two cheques of $1,800 total $3,600.",
                 citations=[BANK_14, BANK_28]))
        inv = investigate(self.split, self.matter, client)
        self.assertEqual((inv.verdict, inv.note), ("explained", ""))
        self.assertEqual(len(inv.citations), 2)
        self.assertEqual([t["tool"] for t in inv.trace], ["find_transactions", "add_amounts"])
        # the tool result was fed back to the model
        self.assertEqual(client.seen[1][-1]["role"], "tool")

    def test_invented_citation_is_overridden(self):
        client = Scripted(call("submit_verdict", verdict="explained", explanation="See the invoice.",
                               citations=["invoices/brightway.pdf :: page 1"]))
        inv = investigate(self.split, self.matter, client)
        self.assertEqual(inv.verdict, "needs_human")
        self.assertEqual(inv.rejected_citations, ["invoices/brightway.pdf :: page 1"])

    def test_explained_without_new_evidence_is_overridden(self):
        original = f"{self.split.evidence[0].doc} :: {self.split.evidence[0].locator}"
        client = Scripted(call("submit_verdict", verdict="explained", explanation="Probably fine.",
                               citations=[original]))
        self.assertEqual(investigate(self.split, self.matter, client).verdict, "needs_human")

    def test_stands_needs_no_citation(self):
        client = Scripted(call("submit_verdict", verdict="stands", explanation="Nothing found.", citations=[]))
        self.assertEqual(investigate(self.split, self.matter, client).verdict, "stands")

    def test_never_submitting_becomes_needs_human(self):
        looping = [call("search_documents", query="brightway")] * 20
        inv = investigate(self.split, self.matter, Scripted(*looping), max_steps=4)
        self.assertEqual((inv.verdict, len(inv.trace)), ("needs_human", 4))

    def test_plain_text_reply_is_nudged_once_then_needs_human(self):
        client = Scripted()
        inv = investigate(self.split, self.matter, client)
        self.assertEqual(inv.verdict, "needs_human")
        self.assertEqual(len(client.seen), 2)

    def test_bad_tool_arguments_do_not_crash(self):
        client = Scripted(
            call("find_transactions", source="ledger", date_from="last August"),
            call("no_such_tool"),
            call("submit_verdict", verdict="stands", explanation="x", citations=[]))
        inv = investigate(self.split, self.matter, client)
        self.assertEqual(inv.verdict, "stands")
        self.assertTrue(all("error" in t["result"] for t in inv.trace))

    def test_model_error_becomes_needs_human(self):
        class Broken:
            def complete(self, *a, **k):
                raise ConnectionError("refused")
        self.assertEqual(investigate(self.split, self.matter, Broken()).verdict, "needs_human")

    def test_judgment_findings_never_reach_the_model(self):
        client = Scripted()
        inv = investigate(self.by_key[("compensation_review", "D-09")], self.matter, client)
        self.assertEqual((inv.verdict, client.seen), ("needs_human", []))

    def test_scoring_and_letter_end_to_end(self):
        """A stand-in that clears the split payment correctly and wrongly dismisses one real problem."""
        def policy(messages):
            brief = messages[1]["content"]
            if "D-11" in brief:
                return call("find_transactions", source="bank", text="brightway")
            if "D-04" in brief:   # the planted, real, unsupported roof repair
                return call("search_documents", query="alder lane property")
            return call("submit_verdict", verdict="stands", explanation="Nothing found.", citations=[])

        def finish(messages):
            brief = messages[1]["content"]
            refs = [r["ref"] for r in json.loads(messages[-1]["content"])]
            new = [r for r in refs if r not in brief]
            return call("submit_verdict", verdict="explained", explanation="Found it.", citations=new[:2])

        class Policy:
            def complete(self, messages, tools=None):
                return finish(messages) if messages[-1]["role"] == "tool" else policy(messages)

        invs = investigate_all(self.findings, self.matter, Policy())
        r = score_investigations(invs, load_truth())
        self.assertEqual(r["wrongly_dismissed"], [("unsupported_entry", "D-04")])
        self.assertEqual(r["decoys_cleared"], [("amount_mismatch", "D-11")])
        letter = draft_request(self.findings, invs)
        self.assertIn("NOT SENT", letter)
        self.assertNotIn("D-11", letter)          # explained items are left out of the letter
        self.assertIn("T3 trust return", letter)  # standing items are in it


if __name__ == "__main__":
    unittest.main()
