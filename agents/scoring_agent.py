"""
agents/scoring_agent.py

PE Scoring Agent — Step 3 of the pipeline.

Evaluates how attractive each company is as a PE buyout target using a
DETERMINISTIC, rule-based scoring function. Every subscore traces back to
a specific financial metric and a threshold defined in config.py — so the
output is fully auditable and reproducible (same input -> same score).

The LLM is used only in the Memo Agent, never here.

Each company receives:
  - 6 subscores (floats 1–5)
  - a weighted final PE attractiveness score (float 1–5)
  - a rationale string per subscore

Scoring model: v3
Six dimensions (weights in parentheses):
  1. scale_fit         (0.22) — market-cap fit vs mid-cap LBO sweet spot
  2. valuation         (0.20) — EV/Revenue; lower = more underwritable
  3. cash_generation   (0.18) — FCF margin + FCF/EBITDA conversion
  4. margin_headroom   (0.16) — EBITDA band (0.6) + gross margin quality (0.4)
  5. growth_quality    (0.12) — banded revenue growth; Rule-of-40 in rationale
  6. leverage_capacity (0.12) — net debt/EBITDA

The v2 model is preserved as score_company_v2 / run_v2 for ablation reference.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (SCORE_WEIGHTS, THRESHOLDS, SCALE_SWEET_SPOT,
                    IMPROVEMENT_BANDS, GROWTH_BANDS,
                    _V2_SCORE_WEIGHTS, _V2_THRESHOLDS)


# ── shared helpers ────────────────────────────────────────────────────────────

def _score_from_bands(value, bands):
    """Map a value to a score using band definitions.

    bands: list of (low, high, score). First band where low <= value < high wins.
    Returns (score, None) on success, (None, 'missing data') when value is None.
    """
    if value is None:
        return None, "missing data"
    for low, high, score in bands:
        if low <= value < high:
            return score, None
    return 1, None


def _score_from_table(value, table, higher_is_better=True):
    """Map a raw metric to a 1-5 score using a threshold table.

    table: list of (bound, score).
    higher_is_better=True  → sorted high-to-low; value >= bound earns score.
    higher_is_better=False → sorted low-to-high; value <= bound earns score.
    Returns (score, None) on success, (None, 'missing data') when value is None.
    """
    if value is None:
        return None, "missing data"
    if higher_is_better:
        for bound, score in table:
            if value >= bound:
                return score, None
        return 1, None
    else:
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
    if 0.5 * lo <= market_cap < lo or hi < market_cap <= 2 * hi:
        return 4, None
    if 0.2 * lo <= market_cap < 0.5 * lo or 2 * hi < market_cap <= 4 * hi:
        return 3, None
    return 2, None


def _weighted_score(subs, weights):
    """Compute weighted score; missing subscores fall back to neutral 3."""
    return round(sum(weights[k] * (subs[k] if subs[k] is not None else 3.0)
                     for k in weights), 3)


# ── v3 scoring (active model) ─────────────────────────────────────────────────

def score_company(profile: dict) -> dict:
    """
    Compute the full PE attractiveness score for one company — v3 model.

    Returns a dict with keys: ticker, company_name, subscores, rationales,
    pe_score, missing_subscores, data_complete.
    """
    T = THRESHOLDS
    subs = {}
    rationales = {}

    # 1. Scale fit ─────────────────────────────────────────────────────────────
    s, miss = _scale_fit_score(profile.get("market_cap"))
    subs["scale_fit"] = s
    rationales["scale_fit"] = (
        f"market cap {_bn(profile.get('market_cap'))}" if not miss else miss)

    # 2. Valuation ─────────────────────────────────────────────────────────────
    s, miss = _score_from_table(profile.get("ev_revenue"),
                                T["valuation"], higher_is_better=False)
    subs["valuation"] = s
    rationales["valuation"] = (
        f"EV/Revenue {_num(profile.get('ev_revenue'))}x" if not miss else miss)

    # 3. Cash generation ───────────────────────────────────────────────────────
    # Sub-signal A: FCF margin
    fcf_s, _ = _score_from_table(profile.get("fcf_margin"),
                                 T["fcf_margin"], higher_is_better=True)
    # Sub-signal B: FCF conversion = FCF / EBITDA (when EBITDA > 0)
    ebitda = profile.get("ebitda")
    fcf    = profile.get("fcf")
    if ebitda and ebitda > 0 and fcf is not None:
        conv   = fcf / ebitda
        conv_s, _ = _score_from_table(conv, T["fcf_conversion"], higher_is_better=True)
        extra  = f", FCF/EBITDA {_num(conv)}x"
    else:
        conv_s = fcf_s          # fall back when EBITDA ≤ 0
        extra  = " (EBITDA≤0, FCF margin used for conversion fallback)"

    valid = [s for s in [fcf_s, conv_s] if s is not None]
    subs["cash_generation"] = round(sum(valid) / len(valid), 3) if valid else None
    rationales["cash_generation"] = (
        f"FCF margin {_pct(profile.get('fcf_margin'))}{extra}"
        if profile.get("fcf_margin") is not None else "missing data")

    # 4. Margin headroom ───────────────────────────────────────────────────────
    # Primary (0.6): EBITDA margin band — directly tests the improvement thesis
    # Secondary (0.4): gross margin quality — software-quality signal
    em   = profile.get("ebitda_margin")
    em_s, _ = _score_from_bands(em, IMPROVEMENT_BANDS)

    gm   = profile.get("gross_margin")
    gm_s, _ = _score_from_table(gm, T["gross_margin"], higher_is_better=True)

    if em_s is not None and gm_s is not None:
        combined = round(0.6 * em_s + 0.4 * gm_s, 3)
    elif em_s is not None:
        combined = float(em_s)
    elif gm_s is not None:
        combined = float(gm_s)
    else:
        combined = None

    subs["margin_headroom"] = combined
    rationales["margin_headroom"] = (
        f"EBITDA margin {_pct(em)}, gross margin {_pct(gm)}"
        if combined is not None else "missing data")

    # 5. Growth quality ────────────────────────────────────────────────────────
    # Banded revenue growth (same bands as v2). Rule-of-40 is computed for
    # transparency but NOT averaged in — it would soften the hyper-growth
    # penalty that correctly down-ranks richly-priced growers.
    rg   = profile.get("revenue_growth")
    rg_s, miss = _score_from_bands(rg, GROWTH_BANDS)

    r40_str = ""
    fm = profile.get("fcf_margin")
    if rg is not None and fm is not None:
        r40_str = f" | Rule-of-40={rg*100 + fm*100:.1f}"

    subs["growth_quality"] = rg_s
    rationales["growth_quality"] = (
        f"rev growth {_pct(rg)}{r40_str}" if not miss else miss)

    # 6. Leverage capacity ─────────────────────────────────────────────────────
    # Net debt / EBITDA only. Interest coverage (EBIT / interest_expense)
    # was evaluated but dropped: it anti-correlates with PE targets because
    # pre-profitability LBO candidates necessarily have negative EBIT coverage.
    nd_s, _ = _score_from_table(profile.get("net_debt_ebitda"),
                                T["net_debt_ebitda"], higher_is_better=False)
    subs["leverage_capacity"] = nd_s
    rationales["leverage_capacity"] = (
        f"net debt/EBITDA {_num(profile.get('net_debt_ebitda'))}x")

    # Weighted final score ─────────────────────────────────────────────────────
    missing = [k for k, v in subs.items() if v is None]
    weighted = _weighted_score(subs, SCORE_WEIGHTS)

    return {
        "ticker":            profile.get("ticker"),
        "company_name":      profile.get("company_name"),
        "subscores":         subs,
        "rationales":        rationales,
        "pe_score":          weighted,
        "missing_subscores": missing,
        "data_complete":     len(missing) == 0,
    }


def run(profiles: dict) -> dict:
    """Score every company with the v3 model. Returns ticker -> score dict."""
    results = {t: score_company(p) for t, p in profiles.items()}
    n_complete = sum(1 for r in results.values() if r["data_complete"])
    print(f"[ScoringAgent] scored {len(results)} companies "
          f"({n_complete} with full data)")
    return results


# ── v2 scoring (archived for ablation) ───────────────────────────────────────

def score_company_v2(profile: dict) -> dict:
    """v2 PE attractiveness score — archived, do not use in production."""
    T2 = _V2_THRESHOLDS
    W2 = _V2_SCORE_WEIGHTS
    subs = {}
    rationales = {}

    s, miss = _scale_fit_score(profile.get("market_cap"))
    subs["scale_fit"] = s
    rationales["scale_fit"] = f"market cap {_bn(profile.get('market_cap'))}" if not miss else miss

    s, miss = _score_from_table(profile.get("ev_revenue"),
                                T2["valuation_attractiveness"], higher_is_better=False)
    subs["valuation_attractiveness"] = s
    rationales["valuation_attractiveness"] = f"EV/Revenue {_num(profile.get('ev_revenue'))}x" if not miss else miss

    s, miss = _score_from_table(profile.get("fcf_margin"),
                                T2["cash_flow_stability"], higher_is_better=True)
    subs["cash_flow_stability"] = s
    rationales["cash_flow_stability"] = f"FCF margin {_pct(profile.get('fcf_margin'))}" if not miss else miss

    s, miss = _score_from_bands(profile.get("ebitda_margin"), IMPROVEMENT_BANDS)
    subs["improvement_headroom"] = s
    em = profile.get("ebitda_margin")
    rationales["improvement_headroom"] = (
        f"EBITDA margin {_pct(em)} ({'room to expand' if (em or 0) < 0.30 else 'already elite'})"
        if not miss else miss)

    s, miss = _score_from_bands(profile.get("revenue_growth"), GROWTH_BANDS)
    subs["growth_moderation"] = s
    rationales["growth_moderation"] = f"revenue growth {_pct(profile.get('revenue_growth'))}" if not miss else miss

    s, miss = _score_from_table(profile.get("net_debt_ebitda"),
                                T2["leverage_capacity"], higher_is_better=False)
    subs["leverage_capacity"] = s
    rationales["leverage_capacity"] = f"net debt/EBITDA {_num(profile.get('net_debt_ebitda'))}x" if not miss else miss

    missing = [k for k, v in subs.items() if v is None]
    return {
        "ticker":            profile.get("ticker"),
        "company_name":      profile.get("company_name"),
        "subscores":         subs,
        "rationales":        rationales,
        "pe_score":          _weighted_score(subs, W2),
        "missing_subscores": missing,
        "data_complete":     len(missing) == 0,
    }


def run_v2(profiles: dict) -> dict:
    """Score every company with the archived v2 model."""
    results = {t: score_company_v2(p) for t, p in profiles.items()}
    n_complete = sum(1 for r in results.values() if r["data_complete"])
    print(f"[ScoringAgent v2] scored {len(results)} companies "
          f"({n_complete} with full data, "
          f"{len(results)-n_complete} used neutral fallback)")
    return results


# ── formatting helpers ────────────────────────────────────────────────────────

def _pct(x):
    return f"{x*100:.1f}%" if x is not None else "n/a"

def _num(x):
    return f"{x:.1f}" if x is not None else "n/a"

def _bn(x):
    return f"${x/1e9:.1f}B" if x is not None else "n/a"


if __name__ == "__main__":
    import json
    demo = {
        "ticker": "TEST", "company_name": "Test Co",
        "fcf_margin": 0.22, "ebitda_margin": 0.20, "gross_margin": 0.72,
        "revenue_growth": 0.12, "net_debt_ebitda": 1.2,
        "ev_revenue": 5.5, "market_cap": 8e9, "ebitda": 200e6, "fcf": 150e6,
    }
    print(json.dumps(score_company(demo), indent=2))
