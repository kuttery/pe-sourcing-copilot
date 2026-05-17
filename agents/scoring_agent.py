"""
agents/scoring_agent.py

PE Scoring Agent — Step 3 of the pipeline.

Evaluates how attractive each company is as a PE buyout target using a
DETERMINISTIC, rule-based scoring function. Every subscore traces back to
a specific financial metric and a threshold defined in config.py — so the
output is fully auditable and reproducible (same input -> same score).

This is a deliberate design choice: the scoring must be defensible for the
evaluation section. The LLM is used only in the Memo Agent, never here.

Each company receives:
  - 6 subscores (1-5 integers)
  - a weighted final PE attractiveness score (1-5 float)
  - a short rationale string per subscore
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (SCORE_WEIGHTS, THRESHOLDS, SCALE_SWEET_SPOT,
                    IMPROVEMENT_BANDS, GROWTH_BANDS)


def _score_from_bands(value, bands):
    """Map a value to a score using band definitions.

    bands: list of (low, high, score). First band where low <= value < high
    wins. Used for metrics where a MIDDLE range is best (improvement
    headroom, growth moderation). Returns (score, None) or (None, reason).
    """
    if value is None:
        return None, "missing data"
    for low, high, score in bands:
        if low <= value < high:
            return score, None
    return 1, None


def _score_from_table(value, table, higher_is_better=True):
    """Map a raw metric to a 1-5 score using a threshold table.

    table: list of (bound, score) sorted high-to-low by bound.
    higher_is_better: if True, value >= bound earns score.
                      if False, value <= bound earns score (table read as
                      ascending bounds, e.g. leverage where low is good).
    Returns (score, None) or (None, reason) if value is missing.
    """
    if value is None:
        return None, "missing data"
    if higher_is_better:
        for bound, score in table:
            if value >= bound:
                return score, None
        return 1, None
    else:
        # ascending bounds: first bound the value is <= wins
        for bound, score in table:
            if value <= bound:
                return score, None
        return 1, None


def _scale_fit_score(market_cap):
    """Score market-cap fit against the mid-cap LBO sweet spot."""
    if market_cap is None:
        return None, "missing data"
    lo, hi = SCALE_SWEET_SPOT
    if lo <= market_cap <= hi:
        return 5, None
    # one order-of-magnitude tolerance bands
    if 0.5 * lo <= market_cap < lo or hi < market_cap <= 2 * hi:
        return 4, None
    if 0.2 * lo <= market_cap < 0.5 * lo or 2 * hi < market_cap <= 4 * hi:
        return 3, None
    return 2, None


def score_company(profile: dict) -> dict:
    """Compute the full PE attractiveness score for one company profile."""
    subs = {}        # subscore name -> int score
    rationales = {}  # subscore name -> human-readable explanation

    # 1. Scale fit — market cap vs mid-cap LBO sweet spot
    s, miss = _scale_fit_score(profile.get("market_cap"))
    subs["scale_fit"] = s
    rationales["scale_fit"] = (
        f"market cap {_bn(profile.get('market_cap'))}" if not miss else miss)

    # 2. Valuation attractiveness — EV/Revenue (LOWER better; underwritable)
    s, miss = _score_from_table(profile.get("ev_revenue"),
                                THRESHOLDS["valuation_attractiveness"], higher_is_better=False)
    subs["valuation_attractiveness"] = s
    rationales["valuation_attractiveness"] = (
        f"EV/Revenue {_num(profile.get('ev_revenue'))}x" if not miss else miss)

    # 3. Cash flow stability — FCF margin (positive cash to service debt)
    s, miss = _score_from_table(profile.get("fcf_margin"),
                                THRESHOLDS["cash_flow_stability"], higher_is_better=True)
    subs["cash_flow_stability"] = s
    rationales["cash_flow_stability"] = (
        f"FCF margin {_pct(profile.get('fcf_margin'))}" if not miss else miss)

    # 4. Improvement headroom — EBITDA margin BAND (moderate = most upside)
    s, miss = _score_from_bands(profile.get("ebitda_margin"), IMPROVEMENT_BANDS)
    subs["improvement_headroom"] = s
    em = profile.get("ebitda_margin")
    rationales["improvement_headroom"] = (
        f"EBITDA margin {_pct(em)} "
        f"({'room to expand' if (em or 0) < 0.30 else 'already elite'})"
        if not miss else miss)

    # 5. Growth moderation — revenue growth BAND (steady > explosive for LBO)
    s, miss = _score_from_bands(profile.get("revenue_growth"), GROWTH_BANDS)
    subs["growth_moderation"] = s
    rationales["growth_moderation"] = (
        f"revenue growth {_pct(profile.get('revenue_growth'))}" if not miss else miss)

    # 6. Leverage capacity — net debt / EBITDA (LOWER better; room to lever)
    s, miss = _score_from_table(profile.get("net_debt_ebitda"),
                                THRESHOLDS["leverage_capacity"], higher_is_better=False)
    subs["leverage_capacity"] = s
    rationales["leverage_capacity"] = (
        f"net debt/EBITDA {_num(profile.get('net_debt_ebitda'))}x" if not miss else miss)

    # Weighted final score. Missing subscores default to a neutral 3 so a
    # single data gap does not unfairly sink a company, but this is flagged.
    missing = [k for k, v in subs.items() if v is None]
    weighted = 0.0
    for name, weight in SCORE_WEIGHTS.items():
        weighted += weight * (subs[name] if subs[name] is not None else 3)

    return {
        "ticker": profile.get("ticker"),
        "company_name": profile.get("company_name"),
        "subscores": subs,
        "rationales": rationales,
        "pe_score": round(weighted, 3),
        "missing_subscores": missing,
        "data_complete": len(missing) == 0,
    }


def run(profiles: dict) -> dict:
    """Score every company. Returns ticker -> score dict."""
    results = {t: score_company(p) for t, p in profiles.items()}
    n_complete = sum(1 for r in results.values() if r["data_complete"])
    print(f"[ScoringAgent] scored {len(results)} companies "
          f"({n_complete} with full data, "
          f"{len(results) - n_complete} used neutral fallback for some subscores)")
    return results


# ---- small formatting helpers -------------------------------------------
def _pct(x):
    return f"{x*100:.1f}%" if x is not None else "n/a"


def _num(x):
    return f"{x:.1f}" if x is not None else "n/a"


def _bn(x):
    return f"${x/1e9:.1f}B" if x is not None else "n/a"


if __name__ == "__main__":
    # quick self-test with a synthetic profile
    demo = {
        "ticker": "TEST", "company_name": "Test Co",
        "fcf_margin": 0.22, "ebitda_margin": 0.28, "revenue_growth": 0.10,
        "net_debt_ebitda": 1.8, "ev_revenue": 5.0, "market_cap": 8e9,
    }
    import json
    print(json.dumps(score_company(demo), indent=2))
