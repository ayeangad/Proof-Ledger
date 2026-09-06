# Distributor Deduction Reconciliation & Evidence Engine — V1

> **Synthetic data. Fictional brand ("Northfork Snack Co."). Built independently to investigate
> a problem named in Minerva/Mars's public materials — not a claim about their internals.**
> Deduction categories are modeled on publicly documented UNFI/KeHE-style formats, not real distributor data.
> Dollar figures are synthetic and represent no real recoverable dollars.

## Run it (one command, reproduces everything)

```bash
uv sync
uv run python run.py        # regenerates data/ + output/ from scratch
uv run python -m unittest discover -s tests -v
open output/report.html     # the deliverable
```

## What it does

Feed: distributor remittance (messy, what they paid) + trade-spend contract/prior accruals (what was expected).
Output per line: classification into `already_accrued / valid_trade_spend / disputable / needs_review`,
a 0–1 confidence, **evidence citing the specific clause/accrual on every decision**, and a journal entry
tied by `source_line_id` (nothing invented or dropped — `len(journals) == len(lines)`).

Safety property: **the model never gets the final say on money above a threshold** —
confidence < 0.75 or disputable > $500 is forced to `needs_review` (`config.json`).

## Layout

- `run.py` — end-to-end pipeline
- `src/schemas.py` — 7 pydantic models (the judged deliverable)
- `src/generator.py` — seeded synthetic data + hand-labeled `data/ground_truth.json` (never touches engine code)
- `src/parsing.py` — invariant gate: `invoice_total − cash_received == Σ|lines|`, fails loudly
- `src/rules.py` → `src/llm_mock.py` → `src/engine.py` — rules pass, mock-LLM pass, threshold routing
- `src/ledger.py` — Decision → JournalEntry (disputable → **receivable, not expense**)
- `src/evaluate.py` — item acc, **$-weighted acc**, confusion matrix, disputable FN-$, review %, time saved + threshold sweep
- `src/report.py` — single self-contained `output/report.html` + `review_queue.html`
- `tests/test_pipeline.py` — 9 invariant/provenance/safety tests
