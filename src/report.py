"""Single self-contained HTML report + review queue. Inline CSS, no build step."""
from __future__ import annotations

import html
import json
from pathlib import Path

E = html.escape


def _money(x) -> str:
    return f"${x:,.2f}"


def build_report(decisions, journals, ev, ground_truth, cfg, out_path: Path) -> None:
    je = {j["source_line_id"]: j for j in journals}
    code_wrong = [d for d in decisions
                  if d["predicted_reason_code"] != ground_truth[d["line_id"]]["reason_code"]]
    routed_safe = [d for d in decisions
                   if d["predicted_reason_code"] == ground_truth[d["line_id"]]["reason_code"]
                   and d["bucket"] == "needs_review"
                   and ground_truth[d["line_id"]]["bucket"] != "needs_review"]
    mism = code_wrong + routed_safe
    # worked examples: prefer the injected hard cases, in fixed showcase order
    showcase_want = ["SB-ALLOW Q3 ADJ", "CHG-BK REF 88213", "REBILL", "OUT OF WINDOW",
                     "ADMIN FEE", "MISC DEDUCT", "SEE BACKUP", "SPOILAGE"]
    picked, seen_ids = [], set()
    for want in showcase_want:
        for d in decisions:
            if want.lower() in (d.get("raw_description") or "").lower() and d["line_id"] not in seen_ids:
                picked.append(d)
                seen_ids.add(d["line_id"])
                break
        if len(picked) >= 5:
            break

    def ex_card(d):
        gt = ground_truth[d["line_id"]]
        j = je[d["line_id"]]
        ok = (d["predicted_reason_code"] == gt["reason_code"] and d["bucket"] == gt["bucket"])
        badge = "MATCH" if ok else "MISS"
        cls = "ok" if ok else "miss"
        evlis = "".join(f"<li>{E(e)}</li>" for e in d["evidence"])
        return f"""<div class="card"><h3>{E(d['raw_description'])} <span class="badge {cls}">{badge}</span></h3>
<p><b>Line</b> {E(d['line_id'])} · invoice {E(d['invoice_id'])} · amount <b>{_money(abs(float(d['amount'])))}</b>
· raw code <code>{E(str(d.get('reason_code_raw')))}</code> · stage <code>{E(d['stage'])}</code></p>
<p><b>Decision:</b> <code>{E(d['predicted_reason_code'])}</code> → <code>{E(d['bucket'])}</code>
(conf {d['confidence']}) &nbsp; <b>Ground truth:</b> <code>{E(gt['reason_code'])}</code> → <code>{E(gt['bucket'])}</code></p>
<p><b>Evidence cited:</b></p><ul>{evlis}</ul>
<p><b>Journal:</b> {E(j['entry_id'])} — Dr <i>{E(j['debit_account'])}</i> / Cr <i>{E(j['credit_account'])}</i>
— {_money(j['amount'])} — <code>{E(j['status'])}</code></p></div>"""

    # confusion matrix html
    codes = ["TRADE_PROMO", "SCAN_ALLOWANCE", "SLOTTING", "SHORTAGE_CLAIM",
             "COMPLIANCE_CHARGEBACK", "SPOILAGE_DAMAGE", "COOP_ADVERTISING", "ADMIN_FEE", "UNKNOWN"]
    conf = ev["confusion"]
    mhead = "".join(f"<th>{c[:6]}</th>" for c in codes)
    mrows = ""
    for actual in codes:
        cells = "".join(f"<td>{conf.get(actual, {}).get(pred, '') or '—'}</td>" for pred in codes)
        mrows += f"<tr><th>{actual[:6]}</th>{cells}</tr>"

    sweep_rows = "".join(
        f"<tr><td>{r['threshold']}</td><td>{r['item_accuracy']:.1%}</td>"
        f"<td>{r['dollar_weighted_accuracy']:.1%}</td><td>{r['review_rate']:.1%}</td>"
        f"<td>{r['disputable_fn_dollar_rate']:.1%}</td></tr>"
        for r in ev["threshold_sweep"])

    if code_wrong:
        fail_cards = "".join(ex_card(d) for d in (code_wrong + routed_safe)[:2])
        fail_intro = (f"The eval found <b>{len(code_wrong)} code error(s)</b> out of {ev['n_lines']} lines. "
                      f"Separately, <b>{len(routed_safe)} line(s)</b> had the right code but were refused auto-posting "
                      "by the safety policy (low confidence or big disputable $) — scored as strict misses, shown second. "
                      "That tradeoff is deliberate: a review costs minutes, a wrongly booked deduction can cost the claim.")
    elif mism:
        fail_cards = "".join(ex_card(d) for d in mism[:2])
        fail_intro = (f"No code errors. All {len(mism)} strict miss(es) are lines where the code was right but the "
                      "safety policy forced <code>needs_review</code> instead of auto-posting. "
                      "First two shown — this is the price of the safety invariant, stated as a cost not a win.")
    else:
        # honest near-miss section when strict accuracy is 100%
        lows = sorted(decisions, key=lambda d: d["confidence"])[:2]
        fail_cards = "".join(ex_card(d) for d in lows)
        fail_intro = ("Strict item accuracy is 100% on this synthetic set — which is itself a warning sign "
                      "(see circularity note). Instead of invented failures, here are the two lowest-confidence "
                      "decisions: the lines closest to being wrong, and why they were fragile.")

    t = ev["reviewer_time"]
    report_html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Northfork Snack Co. — Deduction Reconciliation V1</title>
<style>body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:960px;margin:0 auto;padding:24px;color:#1a1a1a;line-height:1.5}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}}
.kpi{{border:1px solid #ddd;border-radius:10px;padding:12px;background:#fafafa}}.kpi b{{font-size:1.25em}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}th,td{{border:1px solid #ddd;padding:6px 8px;text-align:left;font-size:.9em}}
th{{background:#f3f3f3}}.card{{border:1px solid #ddd;border-radius:10px;padding:14px;margin:14px 0;background:#fff}}
.badge{{font-size:.75em;padding:2px 8px;border-radius:20px}}.ok{{background:#e6f4ea}}.miss{{background:#fdecea}}
code{{background:#f1f1f1;padding:1px 5px;border-radius:4px}}.note{{background:#fff8e1;border:1px solid #ecd27a;border-radius:10px;padding:12px;margin:14px 0}}
.small{{font-size:.85em;color:#555}}</style></head><body>
<h1>Distributor Deduction Reconciliation &amp; Evidence Engine — V1 Report</h1>
<p class="small">Fictional brand <b>Northfork Snack Co.</b> · synthetic remittances modeled on publicly documented
UNFI/KeHE-style deduction categories (not real distributor data) · built independently to investigate a problem
named in Minerva/Mars public materials · not a claim about their internals. Reproduces via <code>python run.py</code>.</p>
<div class="kpis">
<div class="kpi">Processed<b>{_money(ev['total_dollars'])}</b><br><span class="small">{ev['n_lines']} lines, 18 remittances, 3 months</span></div>
<div class="kpi">Auto-reconciled<b>{_money(ev['auto_reconciled_dollars'])}</b><br><span class="small">{ev['auto_post_rate']:.0%} of lines, no human touch</span></div>
<div class="kpi">Flagged disputable<b>{_money(ev['flagged_disputable_dollars'])}</b><br><span class="small">recoverable-money bucket (ground truth)</span></div>
<div class="kpi">Sent to review<b>{_money(ev['sent_to_review_dollars'])}</b><br><span class="small">{ev['review_rate']:.0%} of lines · full queue in review_queue.html</span></div>
</div>
<h2>Evaluation (vs hand-labeled ground_truth.json)</h2>
<table><tr><th>Metric</th><th>Value</th></tr>
<tr><td>Item-level accuracy (strict: code + bucket)</td><td>{ev['item_accuracy']:.1%}</td></tr>
<tr><td><b>$-weighted accuracy</b> (Σ correct $ / Σ total $)</td><td><b>{ev['dollar_weighted_accuracy']:.1%}</b></td></tr>
<tr><td>Reason-code accuracy (code right, incl. safely routed to review)</td><td>{ev['code_accuracy']:.1%} ($-weighted {ev['code_dollar_accuracy']:.1%})</td></tr>
<tr><td>False-negative rate on disputable (count)</td><td>{ev['disputable_fn_count_rate']:.1%}</td></tr>
<tr><td>False-negative rate on disputable ($ — the recoverable-money metric)</td><td>{ev['disputable_fn_dollar_rate']:.1%}</td></tr>
<tr><td>Auto-posted vs review</td><td>{ev['auto_posted']} auto / {ev['sent_to_review']} review</td></tr>
<tr><td>Reviewer time saved</td><td>~{t['hours_saved_per_month']} hrs/month. <span class="small">{E(t['assumption'])}</span></td></tr></table>
<h3>Confusion matrix (rows = truth, cols = predicted)</h3>
<table><tr><th></th>{mhead}</tr>{mrows}</table>
<h3>Threshold tuning (compressed Day-4 — not dropped)</h3>
<p class="small">Spec asked to tune the confidence threshold on what the eval finds and write down what changed and why.
Compressed here into a sweep instead of a full day: {E(ev['threshold_note'])}</p>
<table><tr><th>Threshold</th><th>Item acc</th><th>$-weighted</th><th>Review %</th><th>Disputable FN-$</th></tr>{sweep_rows}</table>
<h2>Worked examples (the ambiguous ones, not the easy ones)</h2>
{"".join(ex_card(d) for d in picked)}
<h2>Where this breaks</h2>
<p>{fail_intro}</p>
{fail_cards}
<h2>Accounting judgment: disputable books to a receivable, not an expense</h2>
<p>A disputable deduction is a <i>claim against the distributor</i>, not a cost already incurred. Booking it to
“Deductions Receivable — Disputed” (Dr receivable / Cr AR) preserves the recovery position and keeps the P&amp;L clean
until the dispute resolves; only confirmed-valid trade spend hits contra-revenue, and only exhausted claims become
expense. Expensing on deduction would understate assets and hide recoverable dollars — the exact leak this system exists to plug.</p>
<div class="note"><b>Two gaps, named explicitly.</b><br>
1) <i>Threshold tuning was compressed, not skipped.</i> The sweep above is the Day-4 activity in miniature; the kept
threshold ({cfg['confidence_threshold']}) and rationale are recorded in <code>output/threshold_tuning.json</code>.<br>
2) <i>Mock-LLM circularity.</i> The <code>llm_mock.py</code> heuristics were written by the same author who injected the
hard cases, so mock accuracy measures “did my heuristic cover my cases” — not model generalization. The transferable
claim is narrower: every uncertain line carries evidence + a confidence, and the routing invariant (low-conf or
disputable &gt; ${cfg['disputable_review_threshold']} → human) holds regardless of which classifier fills the slot. The real test is swapping in a
production model behind the same interface and re-running this harness.</div>
<p class="small">Safety property: the model never gets the final say on money above the threshold — confidence &lt;
{cfg['confidence_threshold']} or disputable &gt; ${cfg['disputable_review_threshold']} is forced to <code>needs_review</code> (config.json).
Reconciliation invariant enforced at parse time: invoice_total − cash_received must equal Σ line amounts.
LLM prompt/response pairs logged to <code>output/llm_log.jsonl</code>.</p>
</body></html>"""
    out_path.write_text(report_html)


def build_review_queue(decisions, out_path: Path) -> None:
    rows = sorted([d for d in decisions if d["bucket"] == "needs_review"],
                  key=lambda d: abs(float(d["amount"])), reverse=True)
    trs = ""
    for d in rows:
        evlis = "".join(f"<li>{E(e)}</li>" for e in d["evidence"])
        trs += (f"<tr><td>{_money(abs(float(d['amount'])))}</td><td>{E(d['line_id'])}</td>"
                f"<td>{E(d.get('raw_description',''))}</td><td>{E(d['predicted_reason_code'])}</td>"
                f"<td>{d['confidence']}</td><td><ul>{evlis}</ul></td>"
                f"<td><button>Accept</button> <button>Override</button></td></tr>")
    out_path.write_text(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Review queue</title>
<style>body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1100px;margin:0 auto;padding:24px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:6px 8px;font-size:.88em}}th{{background:#f3f3f3}}</style>
</head><body><h1>Human review queue ({len(rows)} lines, sorted $ desc)</h1>
<table><tr><th>$</th><th>Line</th><th>Raw</th><th>Code</th><th>Conf</th><th>Evidence</th><th>Action</th></tr>{trs}</table></body></html>""")
