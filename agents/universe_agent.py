"""
agents/universe_agent.py

Universe Agent — dynamically fetches US software companies from Yahoo Finance
screener, then enriches each with full fundamentals via yfinance.

Two modes:
  - run_from_cache(filters)  : load what's already cached (fast, for the app)
  - run_live(filters)        : query Yahoo screener + fetch fresh fundamentals
"""
import os, sys, json, time
import pandas as pd
import yfinance as yf
from yfinance import EquityQuery

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.json")


# ── screener ──────────────────────────────────────────────────────────────────

def _screen_tickers(min_cap: float, max_cap: float) -> list[str]:
    """
    Query Yahoo Finance screener for Technology sector companies in the
    given market-cap range. Returns a list of ticker symbols.
    """
    q = EquityQuery('and', [
        EquityQuery('eq', ['sector', 'Technology']),
        EquityQuery('gt', ['intradaymarketcap', int(min_cap)]),
        EquityQuery('lt', ['intradaymarketcap', int(max_cap)]),
    ])
    results = yf.screen(q, size=250, sortField='intradaymarketcap', sortAsc=False)
    quotes = results.get('quotes', [])
    return [q['symbol'] for q in quotes if q.get('symbol')]


# ── profile builder ───────────────────────────────────────────────────────────

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


def _build_profile(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    info = {}
    try:
        info = tk.info or {}
    except Exception as e:
        pass

    # only keep Software companies
    industry = _safe(info, 'industry', '')
    if 'software' not in industry.lower():
        return None

    market_cap     = _safe(info, 'marketCap')
    revenue        = _safe(info, 'totalRevenue')
    revenue_growth = _safe(info, 'revenueGrowth')
    ebitda         = _safe(info, 'ebitda')
    total_debt     = _safe(info, 'totalDebt')
    cash           = _safe(info, 'totalCash')
    fcf            = _safe(info, 'freeCashflow')
    ev             = _safe(info, 'enterpriseValue')

    ebitda_margin   = (ebitda / revenue)  if (ebitda and revenue) else None
    fcf_margin      = (fcf / revenue)     if (fcf and revenue)    else None
    ev_revenue      = (ev / revenue)      if (ev and revenue)     else None
    net_debt        = (total_debt - cash) if (total_debt is not None and cash is not None) else None
    net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

    return {
        "ticker":          ticker,
        "company_name":    _safe(info, 'shortName') or ticker,
        "description":     _safe(info, 'longBusinessSummary'),
        "industry":        industry,
        "sector_yf":       _safe(info, 'sector'),
        "market_cap":      market_cap,
        "revenue":         revenue,
        "ebitda":          ebitda,
        "ebitda_margin":   ebitda_margin,
        "fcf":             fcf,
        "fcf_margin":      fcf_margin,
        "revenue_growth":  revenue_growth,
        "total_debt":      total_debt,
        "cash":            cash,
        "net_debt":        net_debt,
        "net_debt_ebitda": net_debt_ebitda,
        "enterprise_value": ev,
        "ev_revenue":      ev_revenue,
        "data_complete":   all(x is not None for x in
                               [market_cap, revenue, ebitda_margin, revenue_growth]),
    }


# ── public API ────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, 'w') as f:
        json.dump(cache, f, indent=2)


def run_live(filters: dict, progress_cb=None) -> dict:
    """
    Full live fetch:
      1. Screen Yahoo Finance for tickers matching market-cap range
      2. Fetch fundamentals for uncached tickers
      3. Update cache and return all profiles

    progress_cb(done, total, ticker) — optional callback for UI progress bar.
    """
    min_cap = filters.get('min_market_cap', 1e9)
    max_cap = filters.get('max_market_cap', 60e9)

    print(f"[UniverseAgent] screening Yahoo Finance for Technology ${min_cap/1e9:.0f}B–${max_cap/1e9:.0f}B ...")
    tickers = _screen_tickers(min_cap, max_cap)
    print(f"[UniverseAgent] screener returned {len(tickers)} tickers")

    cache = load_cache()
    to_fetch = [t for t in tickers if t not in cache]
    print(f"[UniverseAgent] fetching fundamentals for {len(to_fetch)} new tickers ...")

    for i, ticker in enumerate(to_fetch):
        if progress_cb:
            progress_cb(i, len(to_fetch), ticker)
        profile = _build_profile(ticker)
        if profile:
            cache[ticker] = profile
        time.sleep(0.4)

    save_cache(cache)
    if progress_cb:
        progress_cb(len(to_fetch), len(to_fetch), "done")

    # return only tickers that came from screener + are software
    return {t: cache[t] for t in tickers if t in cache}


def run_from_cache(filters: dict) -> dict:
    """Return all cached profiles, optionally filtered by market cap."""
    cache = load_cache()
    min_cap = filters.get('min_market_cap', 0)
    max_cap = filters.get('max_market_cap', 1e18)
    return {
        t: p for t, p in cache.items()
        if p.get('market_cap') and min_cap <= p['market_cap'] <= max_cap
    }


# legacy shim so main.py still works
def run(filters: dict) -> pd.DataFrame:
    import pandas as pd
    universe_path = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")
    df = pd.read_csv(universe_path)
    n_start = len(df)
    sector = filters.get("sector")
    if sector:
        df = df[df["sector"].str.lower() == sector.lower()]
    df = df.reset_index(drop=True)
    print(f"[UniverseAgent] {n_start} companies -> {len(df)} after static filters "
          f"(sector={sector}, geography={filters.get('geography')})")
    return df
