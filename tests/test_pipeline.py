"""Pipeline tests — stdlib unittest, run with: uv run python -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "config.json").read_text())
        cls.decisions = json.loads((ROOT / "output" / "decisions.json").read_text())
        cls.journals = json.loads((ROOT / "output" / "journal_entries.json").read_text())
        cls.eval = json.loads((ROOT / "output" / "eval.json").read_text())
        cls.gt = json.loads((ROOT / "data" / "ground_truth.json").read_text())
        cls.rems = [json.loads(p.read_text())
                    for p in sorted((ROOT / "data" / "remittances").glob("*.json"))]

    def test_invariant_holds_everywhere(self):
        for r in self.rems:
            expect = round(r["invoice_total"] - r["cash_received"], 2)
            actual = round(sum(abs(float(l["amount"])) for l in r["lines"]), 2)
            self.assertAlmostEqual(expect, actual, places=2, msg=r["remittance_id"])

    def test_every_decision_has_evidence_and_confidence(self):
        for d in self.decisions:
            self.assertTrue(d["evidence"], d["line_id"])
            self.assertGreaterEqual(d["confidence"], 0.0)
            self.assertLessEqual(d["confidence"], 1.0)
            self.assertTrue(d["journal_entry_id"], d["line_id"])

    def test_every_journal_has_provenance(self):
        line_ids = {d["line_id"] for d in self.decisions}
        for j in self.journals:
            self.assertTrue(j["source_line_id"], j["entry_id"])
            self.assertIn(j["source_line_id"], line_ids)
        self.assertEqual(len(self.journals), len(self.decisions))  # nothing invented or dropped

    def test_unknown_never_auto_books(self):
        for d in self.decisions:
            if d["predicted_reason_code"] == "UNKNOWN":
                self.assertEqual(d["bucket"], "needs_review", d["line_id"])
        for d, j in zip(self.decisions, self.journals):
            if d["predicted_reason_code"] == "UNKNOWN":
                self.assertEqual(j["status"], "pending_review", d["line_id"])

    def test_big_disputable_never_auto_posts(self):
        thr = float(self.cfg["disputable_review_threshold"])
        for d, j in zip(self.decisions, self.journals):
            if d["bucket"] == "disputable":
                self.assertLessEqual(abs(float(d["amount"])), thr, d["line_id"])
            if abs(float(d["amount"])) > thr and d["predicted_reason_code"] != "UNKNOWN":
                gt_b = self.gt[d["line_id"]]["bucket"]
                if gt_b == "disputable":
                    self.assertEqual(d["bucket"], "needs_review", d["line_id"])

    def test_disputable_books_to_receivable_not_expense(self):
        for d, j in zip(self.decisions, self.journals):
            if d["bucket"] == "disputable":
                self.assertEqual(j["debit_account"], "Deductions Receivable — Disputed")
            if d["bucket"] == "valid_trade_spend":
                self.assertIn("contra-revenue", j["debit_account"])

    def test_metrics_sane(self):
        for k in ("item_accuracy", "dollar_weighted_accuracy",
                  "disputable_fn_dollar_rate", "review_rate"):
            self.assertGreaterEqual(self.eval[k], 0.0, k)
            self.assertLessEqual(self.eval[k], 1.0, k)
        self.assertGreater(self.eval["total_dollars"], 0)

    def test_ground_truth_covers_every_line(self):
        self.assertEqual(set(self.gt.keys()), {d["line_id"] for d in self.decisions})

    def test_report_artifacts_exist(self):
        for f in ("report.html", "review_queue.html", "llm_log.jsonl",
                  "threshold_tuning.json", "eval.json"):
            self.assertTrue((ROOT / "output" / f).exists(), f)


if __name__ == "__main__":
    unittest.main()
