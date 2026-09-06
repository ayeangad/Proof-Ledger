# One-pager: what I noticed, built, measured, and want to learn

## Noticed (public materials only)
Minerva/Mars talk about distributor-data fragmentation and trade-spend leakage: brands invoice,
distributors deduct opaquely (chargebacks, shortages, fees stacked on fees), and finance teams true-up
in spreadsheets weeks later. The안군 hard part isn't OCR — it's the accounting judgment per line:
was this deduction already accrued, contractually valid, or a disputable claim to recover?

## Built
A 5-stage reconciliation engine on synthetic data (fictional "Northfork Snack Co.", 18 remittances /
~130 lines / 3 months, UNFI-style + KeHE-style formats): pydantic schemas with provenance
(`source_line_id` on every journal, `evidence` on every decision) → invariant-gated parsing →
rules pass (synonym + amount/timing match, ~free) → mock-LLM pass behind a swappable interface
→ confidence + dollar-threshold routing → ledger (disputable → **Deductions Receivable, not expense**)
→ eval harness vs a hand-labeled answer key → single-file HTML report. One command: `python run.py`.

## Measured
See `output/report.html` for live numbers. The metrics that matter: **$-weighted accuracy**
(not item count), **false-negative $ rate on disputable** (recoverable money missed — the costliest
error), and **review %** (the labor lever). Threshold sweep over 0.60–0.85 is recorded with its
rationale in `output/threshold_tuning.json` — compressed from the spec's Day-4 tuning day, not dropped.

## Honest caveats
- **Threshold:** kept value vs sweep pick is documented; re-tune on real data before trusting it.
- **Circularity:** the mock LLM was written to catch the cases I also injected — its accuracy is a
  pipeline-integration signal, not a model-generalization claim. The durable part is the routing
  invariant and the evidence/provenance schema, which survive the swap to a real model.

## Want to learn (to go production-credible)
1. Real remittance/backup formats per distributor (column layouts, code dictionaries, cryptic shorthand).
2. Real contract structures (how promo/scan/slotting/coop terms are actually parameterized).
3. Reviewer workflow: who clears the queue, what override reasons recur, what SLAs apply.
4. ERP posting requirements (which accounts, which memo fields, what “pending_review” maps to).
