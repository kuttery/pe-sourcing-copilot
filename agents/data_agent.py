"""
agents/data_agent.py

Data Retrieval Agent — Step 2 of the pipeline.

Collects financial + qualitative data for each candidate company using
yfinance. Results are cached to data/cache.json so that repeated runs
(especially evaluation runs) are fast, reproducible, and resilient to
yfinance rate limits / outages.

Output per company: a structured JSON profile.
"""
import os
import json
import time
import pandas as pd
import yfinance as yf

# Evaluation uses the hand-labelled eval_cache (never the live screener cache)
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "eval_cache.json")


def _safe(d, key, default=None):
    """Safely pull a value from a dict, treating None / NaN as missing."""
    v = d.get(key, default)
    if v is None:
        return default
    try:
        if isinstance(v, float) and pd.isna(v):
            return default
    except (TypeError, ValueError):
        pass
    return v


def _build_profile(ticker: str) -> dict:
    """Fetch a single company's profile from yfinance.

    Returns a structured dict. Missing fields are left as None so the
    scoring agent can handle gaps explicitly rather than crashing.
    """
    tk = yf.Ticker(ticker)
    info = {}
    try:
        info = tk.info or {}
    except Exception as e:
        print(f"  [DataAgent] WARN {ticker}: info fetch failed ({e})")

    market_cap = _safe(info, "marketCap")
    revenue = _safe(info, "totalRevenue")
    revenue_growth = _safe(info, "revenueGrowth")
    ebitda = _safe(info, "ebitda")
    total_debt = _safe(info, "totalDebt")
    cash = _safe(info, "totalCash")
    fcf = _safe(info, "freeCashflow")
    ev = _safe(info, "enterpriseValue")

    # Derived ratios — only computed when inputs are present
    ebitda_margin = (ebitda / revenue) if (ebitda and revenue) else None
    fcf_margin = (fcf / revenue) if (fcf and revenue) else None
    ev_revenue = (ev / revenue) if (ev and revenue) else None
    net_debt = (total_debt - cash) if (total_debt is not None and cash is not None) else None
    net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

    profile = {
        "ticker": ticker,
        "company_name": _safe(info, "shortName") or ticker,
        "description": _safe(info, "longBusinessSummary"),
        "industry": _safe(info, "industry"),
        "sector_yf": _safe(info, "sector"),
        "market_cap": market_cap,
        "revenue": revenue,
        "ebitda": ebitda,
        "ebitda_margin": ebitda_margin,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
        "revenue_growth": revenue_growth,
        "total_debt": total_debt,
        "cash": cash,
        "net_debt": net_debt,
        "net_debt_ebitda": net_debt_ebitda,
        "enterprise_value": ev,
        "ev_revenue": ev_revenue,
        "data_complete": all(x is not None for x in
                             [market_cap, revenue, ebitda_margin, revenue_growth]),
    }
    return profile


def run(universe_df: pd.DataFrame, use_cache: bool = True) -> dict:
    """Retrieve profiles for every ticker in the universe.

    Args:
        universe_df: output of the Universe Agent.
        use_cache: if True, load cached profiles and only fetch missing ones.

    Returns:
        dict mapping ticker -> profile dict.
    """
    cache = {}
    if use_cache and os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        print(f"[DataAgent] loaded {len(cache)} cached profiles")

    profiles = {}
    fetched = 0
    for ticker in universe_df["ticker"]:
        if ticker in cache:
            profiles[ticker] = cache[ticker]
            continue
        print(f"  [DataAgent] fetching {ticker} ...")
        profiles[ticker] = _build_profile(ticker)
        cache[ticker] = profiles[ticker]
        fetched += 1
        time.sleep(1.0)  # be polite to yfinance

    # Persist updated cache
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    complete = sum(1 for p in profiles.values() if p.get("data_complete"))
    print(f"[DataAgent] {len(profiles)} profiles ready "
          f"({fetched} newly fetched, {complete} with complete core data)")
    return profiles


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agents import universe_agent
    from config import DEFAULT_FILTERS
    uni = universe_agent.run(DEFAULT_FILTERS)
    profs = run(uni)
    # quick sanity print
    for t, p in list(profs.items())[:3]:
        print(t, "| mktcap:", p["market_cap"], "| ebitda_margin:", p["ebitda_margin"])
