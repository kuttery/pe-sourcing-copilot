"""
main.py

Coordinator Agent — Step 5 of the pipeline and the project entry point.

Orchestrates the full agentic workflow:

    User filters
        -> Universe Agent      (define candidate universe)
        -> Data Retrieval Agent (fetch financial profiles)
        -> PE Scoring Agent     (deterministic attractiveness scoring)
        -> rank + select top-K
        -> Memo Generation Agent (LLM sourcing memos for top-K)
        -> write outputs

Outputs (written to outputs/):
    - ranked_shortlist.csv : every company, score, subscores, label
    - memo_<TICKER>.md     : one sourcing memo per top-K company

Run:  python main.py
"""
import os
import sys
import csv

sys.path.insert(0, os.path.dirname(__file__))

from config import DEFAULT_FILTERS, TOP_K
from agents import universe_agent, data_agent, scoring_agent, memo_agent

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")


def apply_market_cap_filter(universe_df, profiles, filters):
    """Drop companies outside the market-cap band (needs live data)."""
    lo = filters.get("min_market_cap")
    hi = filters.get("max_market_cap")
    if lo is None and hi is None:
        return universe_df

    keep = []
    for ticker in universe_df["ticker"]:
        mc = profiles.get(ticker, {}).get("market_cap")
        if mc is None:
            keep.append(ticker)  # keep unknowns rather than silently dropping
            continue
        if lo is not None and mc < lo:
            continue
        if hi is not None and mc > hi:
            continue
        keep.append(ticker)

    filtered = universe_df[universe_df["ticker"].isin(keep)].reset_index(drop=True)
    print(f"[Coordinator] market-cap filter: {len(universe_df)} -> {len(filtered)}")
    return filtered


def write_shortlist(scores, labels, path):
    """Write the full ranked shortlist to CSV."""
    rows = sorted(scores.values(), key=lambda s: s["pe_score"], reverse=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "ticker", "company_name", "pe_score",
                    "scale_fit", "valuation_attractiveness", "cash_flow_stability",
                    "improvement_headroom", "growth_moderation", "leverage_capacity",
                    "data_complete", "pe_acquired_label"])
        for i, s in enumerate(rows, 1):
            sub = s["subscores"]
            w.writerow([i, s["ticker"], s["company_name"], s["pe_score"],
                        sub["scale_fit"], sub["valuation_attractiveness"],
                        sub["cash_flow_stability"], sub["improvement_headroom"],
                        sub["growth_moderation"], sub["leverage_capacity"],
                        s["data_complete"], labels.get(s["ticker"], "")])
    return rows


def run(filters=None):
    filters = filters or DEFAULT_FILTERS
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 64)
    print("PE SOURCING COPILOT — agentic pipeline")
    print("=" * 64)

    # Step 1: Universe
    universe = universe_agent.run(filters)
    labels = dict(zip(universe["ticker"], universe["pe_acquired"]))

    # Step 2: Data retrieval
    profiles = data_agent.run(universe)

    # Step 2b: market-cap filter (needs live data)
    universe = apply_market_cap_filter(universe, profiles, filters)
    profiles = {t: profiles[t] for t in universe["ticker"] if t in profiles}
    labels = {t: labels[t] for t in profiles}

    # Step 3: Scoring
    scores = scoring_agent.run(profiles)

    # Step 4: rank + select top-K
    ranked = sorted(scores.values(), key=lambda s: s["pe_score"], reverse=True)
    top_tickers = [s["ticker"] for s in ranked[:TOP_K]]
    print(f"[Coordinator] top-{TOP_K} shortlist: {', '.join(top_tickers)}")

    # Step 5: Memos for top-K
    memos = memo_agent.run(profiles, scores, top_tickers)

    # ---- write outputs ----------------------------------------------------
    shortlist_path = os.path.join(OUTPUT_DIR, "ranked_shortlist.csv")
    write_shortlist(scores, labels, shortlist_path)
    print(f"[Coordinator] wrote {shortlist_path}")

    for ticker, memo in memos.items():
        mp = os.path.join(OUTPUT_DIR, f"memo_{ticker}.md")
        with open(mp, "w") as f:
            f.write(memo)
    print(f"[Coordinator] wrote {len(memos)} memo files to {OUTPUT_DIR}/")

    # ---- console summary --------------------------------------------------
    print("\n" + "=" * 64)
    print(f"TOP-{TOP_K} PE TARGET SHORTLIST")
    print("=" * 64)
    for i, s in enumerate(ranked[:TOP_K], 1):
        lab = " [PE-acquired]" if labels.get(s["ticker"]) else ""
        print(f"{i}. {s['company_name']} ({s['ticker']}) "
              f"— PE score {s['pe_score']}/5{lab}")
    print("\nDone. See outputs/ for the full shortlist and memos.")
    return scores, memos


if __name__ == "__main__":
    run()
