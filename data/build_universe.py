"""
data/build_universe.py

Fetches all US-listed Software companies from yfinance's Industry objects,
retrieves financial profiles, and writes them to data/cache.json.

Preserves existing cache entries (including manually-patched PE-acquired
company profiles) and only fetches tickers not already cached.

Run with:  python3 data/build_universe.py
"""
import os, sys, json, time
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CACHE_PATH  = os.path.join(os.path.dirname(__file__), "cache.json")
UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "universe.csv")

INDUSTRIES = ["software-application", "software-infrastructure"]


def _safe(d, key, default=None):
    v = d.get(key, default)
    if v is None:
        return default
    try:
        if isinstance(v, float) and pd.isna(v):
            return default
    except Exception:
        pass
    return v


def build_profile(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    info = {}
    try:
        info = tk.info or {}
    except Exception as e:
        print(f"  WARN {ticker}: {e}")

    market_cap     = _safe(info, "marketCap")
    revenue        = _safe(info, "totalRevenue")
    revenue_growth = _safe(info, "revenueGrowth")
    ebitda         = _safe(info, "ebitda")
    total_debt     = _safe(info, "totalDebt")
    cash           = _safe(info, "totalCash")
    fcf            = _safe(info, "freeCashflow")
    ev             = _safe(info, "enterpriseValue")

    ebitda_margin   = (ebitda / revenue)   if (ebitda and revenue) else None
    fcf_margin      = (fcf / revenue)      if (fcf and revenue) else None
    ev_revenue      = (ev / revenue)       if (ev and revenue) else None
    net_debt        = (total_debt - cash)  if (total_debt is not None and cash is not None) else None
    net_debt_ebitda = (net_debt / ebitda)  if (net_debt is not None and ebitda and ebitda > 0) else None

    return {
        "ticker":        ticker,
        "company_name":  _safe(info, "shortName") or ticker,
        "description":   _safe(info, "longBusinessSummary"),
        "industry":      _safe(info, "industry"),
        "sector_yf":     _safe(info, "sector"),
        "market_cap":    market_cap,
        "revenue":       revenue,
        "ebitda":        ebitda,
        "ebitda_margin": ebitda_margin,
        "fcf":           fcf,
        "fcf_margin":    fcf_margin,
        "revenue_growth": revenue_growth,
        "total_debt":    total_debt,
        "cash":          cash,
        "net_debt":      net_debt,
        "net_debt_ebitda": net_debt_ebitda,
        "enterprise_value": ev,
        "ev_revenue":    ev_revenue,
        "data_complete": all(x is not None for x in
                             [market_cap, revenue, ebitda_margin, revenue_growth]),
    }


def main():
    # load existing cache
    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        print(f"Loaded {len(cache)} existing cached profiles")

    # collect tickers from yfinance industry objects
    tickers = set()
    for key in INDUSTRIES:
        ind = yf.Industry(key)
        tickers.update(ind.top_companies.index.tolist())
        tickers.update(ind.top_growth_companies.index.tolist())
    print(f"Found {len(tickers)} tickers across software industries")

    # fetch only new ones
    new_tickers = [t for t in sorted(tickers) if t not in cache]
    print(f"Fetching {len(new_tickers)} new profiles (skipping {len(tickers)-len(new_tickers)} cached)...")

    fetched, skipped = 0, 0
    for i, ticker in enumerate(new_tickers, 1):
        print(f"  [{i}/{len(new_tickers)}] {ticker} ...", end=" ", flush=True)
        p = build_profile(ticker)
        if p.get("market_cap"):
            cache[ticker] = p
            fetched += 1
            print(f"ok — ${p['market_cap']/1e9:.1f}B mktcap")
        else:
            skipped += 1
            print("skipped (no market cap data)")
        time.sleep(0.5)

    # save
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"\nDone. Fetched {fetched}, skipped {skipped}. Cache now has {len(cache)} profiles.")
    print(f"Cache saved to {CACHE_PATH}")


if __name__ == "__main__":
    main()
