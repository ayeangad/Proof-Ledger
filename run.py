"""One command: generate -> parse -> reconcile -> ledger -> evaluate -> report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import generator  # noqa: E402
from src.engine import reconcile  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.ledger import build_ledger  # noqa: E402
from src.parsing import load_all  # noqa: E402
from src.report import build_report, build_review_queue  # noqa: E402
from src.schemas import Decision, JournalEntry, Remittance  # noqa: E402

OUT = ROOT / "output"


def main() -> None:
    cfg = json.loads((ROOT / "config.json").read_text())
    OUT.mkdir(exist_ok=True)

    print("== 1/6 generate (seeded, fictional) ==")
    generator.main()

    print("== 2/6 parse + invariant ==")
    rems = load_all()
    print(f"   {len(rems)} remittances, {sum(len(r.lines) for r in rems)} lines — invariant holds")

    agreement = json.loads((ROOT / "data" / "agreement.json").read_text())
    accruals = json.loads((ROOT / "data" / "accruals.json").read_text())
    gt = json.loads((ROOT / "data" / "ground_truth.json").read_text())

    print("== 3/6 reconcile (rules -> mock LLM -> routing) ==")
    decisions, llm_log = reconcile(rems, agreement, accruals, cfg)
    # validate through pydantic before writing
    for d in decisions:
        Decision(**{k: d[k] for k in
                    ("line_id", "predicted_reason_code", "bucket", "confidence",
                     "evidence", "matched_accrual_id", "journal_entry_id", "stage")})
    (OUT / "decisions.json").write_text(json.dumps(decisions, indent=2))
    (OUT / "llm_log.jsonl").write_text("\n".join(json.dumps(e) for e in llm_log) + "\n")
    n_rules = sum(1 for d in decisions if d["stage"] == "rules")
    print(f"   {len(decisions)} decisions ({n_rules} rules, {len(decisions) - n_rules} mock-LLM), "
          f"{sum(1 for d in decisions if d['bucket'] == 'needs_review')} routed to review")

    print("== 4/6 ledger ==")
    journals = build_ledger(decisions)
    for j in journals:
        JournalEntry(**j)
    (OUT / "journal_entries.json").write_text(json.dumps(journals, indent=2))
    build_review_queue(decisions, OUT / "review_queue.html")

    print("== 5/6 evaluate (incl. threshold sweep) ==")
    ev = evaluate(decisions, gt, cfg)
    (OUT / "eval.json").write_text(json.dumps(ev, indent=2))
    (OUT / "threshold_tuning.json").write_text(json.dumps({
        "kept": ev["threshold_kept"], "sweep_pick": ev["threshold_chosen_by_sweep"],
        "sweep": ev["threshold_sweep"], "note": ev["threshold_note"],
    }, indent=2))
    print(f"   item {ev['item_accuracy']:.1%} | $-weighted {ev['dollar_weighted_accuracy']:.1%} | "
          f"disputable FN-$ {ev['disputable_fn_dollar_rate']:.1%} | review {ev['review_rate']:.0%}")

    print("== 6/6 report ==")
    build_report(decisions, journals, ev, gt, cfg, OUT / "report.html")
    print("   output/report.html + output/review_queue.html written")
    print("DONE — open output/report.html")


if __name__ == "__main__":
    main()
