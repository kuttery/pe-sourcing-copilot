"""
eval/evaluate.py

Evaluation runner for the PE Sourcing Copilot.

Produces two rankings:
  1. Agentic  — companies sorted by PE score (v3 model)
  2. Baseline — naive market-cap sort

Scores both against the verified `pe_acquired` ground truth and prints
Precision@K, Recall@K, NDCG@K plus a top-10 side-by-side shortlist.

Run:  python eval/evaluate.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DEFAULT_FILTERS, EVAL_K_VALUES
from agents import universe_agent, data_agent, scoring_agent, baseline
from eval.metrics import evaluate_ranking


def build_labels(universe_df):
    """ticker -> 1/0 ground-truth label."""
    return dict(zip(universe_df["ticker"], universe_df["pe_acquired"]))


def agentic_ranking(scores):
    """Tickers sorted by PE score descending."""
    ordered = sorted(scores.values(), key=lambda s: s["pe_score"], reverse=True)
    return [s["ticker"] for s in ordered]


def run():
    print("=" * 64)
    print("PE SOURCING COPILOT — EVALUATION")
    print("=" * 64)

    universe = universe_agent.run(DEFAULT_FILTERS)
    labels   = build_labels(universe)
    n_pos    = sum(labels.values())
    print(f"\nGround truth: {n_pos} PE-acquired / {len(labels)} companies "
          f"(base rate {n_pos/len(labels):.1%})\n")

    profiles      = data_agent.run(universe)
    scores        = scoring_agent.run(profiles)

    rank_agentic  = agentic_ranking(scores)
    rank_baseline = baseline.rank(profiles)

    eval_agentic  = evaluate_ranking(rank_agentic,  labels, EVAL_K_VALUES)
    eval_baseline = evaluate_ranking(rank_baseline, labels, EVAL_K_VALUES)

    # ── comparison table ───────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print("RESULTS — Agentic PE pipeline  vs.  Market-cap baseline")
    print("=" * 64)
    print(f"{'Metric':<16}{'K':<5}{'Agentic':<12}{'Baseline':<12}{'Delta':<10}")
    print("-" * 64)
    for metric in ["precision", "recall", "ndcg"]:
        for k in EVAL_K_VALUES:
            a = eval_agentic[k][metric]
            b = eval_baseline[k][metric]
            d = round(a - b, 3)
            sign = "+" if d >= 0 else ""
            print(f"{metric:<16}{k:<5}{a:<12.3f}{b:<12.3f}{sign}{d:<10}")
        print("-" * 64)

    # ── top-10 side by side ────────────────────────────────────────────────
    print("\nTop-10 shortlist (✓ = actually PE-acquired):")
    print(f"{'Rank':<6}{'Agentic':<28}{'Baseline':<28}")
    for i in range(min(10, len(rank_agentic))):
        ta = rank_agentic[i]
        tb = rank_baseline[i]
        ma = "✓" if labels.get(ta) else " "
        mb = "✓" if labels.get(tb) else " "
        sc = scores[ta]["pe_score"]
        print(f"{i+1:<6}{ta+' '+ma:<28}{tb+' '+mb:<28}  (score {sc:.2f})")

    # ── subscore detail for every company ──────────────────────────────────
    print("\n\nSUBSCORE DETAIL (sorted by PE score):")
    print(f"{'Ticker':<8} {'Label':>5}  {'Score':>5}  "
          f"{'scale':>6} {'val':>6} {'cashgen':>8} {'marg':>6} {'grow':>6} {'lev':>6}")
    print("-" * 68)
    for tk in rank_agentic:
        s   = scores[tk]
        ss  = s["subscores"]
        lbl = "POS" if labels.get(tk) else "neg"
        def _f(v): return f"{v:.2f}" if v is not None else "  n/a"
        print(f"{tk:<8} {lbl:>5}  {s['pe_score']:>5.2f}  "
              f"{_f(ss.get('scale_fit')):>6} "
              f"{_f(ss.get('valuation')):>6} "
              f"{_f(ss.get('cash_generation')):>8} "
              f"{_f(ss.get('margin_headroom')):>6} "
              f"{_f(ss.get('growth_quality')):>6} "
              f"{_f(ss.get('leverage_capacity')):>6}")

    return {"agentic": eval_agentic, "baseline": eval_baseline}


if __name__ == "__main__":
    run()
