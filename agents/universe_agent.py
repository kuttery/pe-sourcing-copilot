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

# Live screener cache — separate from the hand-labelled eval cache
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "live_cache.json")

REGION_LABELS = {
    'us': 'United States', 'gb': 'United Kingdom', 'de': 'Germany',
    'fr': 'France',        'ca': 'Canada',          'au': 'Australia',
    'jp': 'Japan',         'cn': 'China',            'hk': 'Hong Kong',
    'in': 'India',         'se': 'Sweden',           'nl': 'Netherlands',
    'il': 'Israel',        'kr': 'South Korea',      'sg': 'Singapore',
    'tw': 'Taiwan',        'br': 'Brazil',            'ch': 'Switzerland',
    'es': 'Spain',         'it': 'Italy',             'ie': 'Ireland',
    'dk': 'Denmark',       'no': 'Norway',            'fi': 'Finland',
    'be': 'Belgium',       'nz': 'New Zealand',       'mx': 'Mexico',
}

ALL_SECTORS = [
    'Technology', 'Communication Services', 'Financial Services',
    'Healthcare', 'Consumer Cyclical', 'Consumer Defensive',
    'Industrials', 'Basic Materials', 'Real Estate', 'Energy', 'Utilities',
]


# ── screener ──────────────────────────────────────────────────────────────────

def _screen_tickers(min_cap: float, max_cap: float,
                    regions=None, sectors=None) -> list:
    """
    Query Yahoo Finance screener for each region × sector combination.
    Returns a deduplicated list of ticker symbols.
    """
    regions = regions or ['us']
    sectors = sectors or ['Technology']

    all_tickers = []
    for region in regions:
        for sector in sectors:
            clauses = [
                EquityQuery('eq', ['region', region]),
                EquityQuery('eq', ['sector', sector]),
                EquityQuery('gt', ['intradaymarketcap', int(min_cap)]),
                EquityQuery('lt', ['intradaymarketcap', int(max_cap)]),
            ]
            try:
                results = yf.screen(EquityQuery('and', clauses),
                                    size=250, sortField='intradaymarketcap', sortAsc=False)
                all_tickers.extend(
                    qt['symbol'] for qt in results.get('quotes', []) if qt.get('symbol')
                )
            except Exception as e:
                print(f"  [UniverseAgent] screener error ({region}/{sector}): {e}")

    seen, unique = set(), []
    for t in all_tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


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
        "country":         _safe(info, 'country'),
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
      1. Screen Yahoo Finance for tickers matching all filters
      2. Fetch fundamentals for uncached tickers
      3. Update cache and return all profiles

    progress_cb(done, total, ticker) — optional callback for UI progress bar.
    """
    min_cap = filters.get('min_market_cap', 1e9)
    max_cap = filters.get('max_market_cap', 60e9)
    regions = filters.get('regions') or ['us']
    sectors = filters.get('sectors') or ['Technology']

    print(f"[UniverseAgent] screening Yahoo Finance "
          f"regions={regions} sectors={sectors} "
          f"${min_cap/1e9:.0f}B–${max_cap/1e9:.0f}B ...")
    tickers = _screen_tickers(min_cap, max_cap, regions=regions, sectors=sectors)
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

    # return only tickers that came from screener + are software, deduplicated
    raw = {t: cache[t] for t in tickers if t in cache}
    return deduplicate_profiles(raw)


def deduplicate_profiles(profiles: dict) -> dict:
    """
    Remove cross-listing duplicates (e.g. KSOLVES.NS and KSOLVES.BO are the
    same company on two Indian exchanges). Keep the entry with the most complete
    data; prefer the ticker without a dot-suffix (US listings) or the first seen.
    """
    # Deduplicate by base ticker (strip exchange suffix like .NS, .BO, .L, .PA)
    # INFOBEAN.BO and INFOBEAN.NS -> both have base "INFOBEAN" -> keep one
    seen = {}  # base_ticker -> ticker
    result = {}
    for ticker, p in profiles.items():
        base = ticker.split('.')[0].upper()
        if base not in seen:
            seen[base] = ticker
            result[ticker] = p
        else:
            # prefer the ticker without any suffix (US listings have no dot)
            existing = seen[base]
            if '.' not in ticker:
                del result[existing]
                seen[base] = ticker
                result[ticker] = p
            # else keep existing
    return result


def run_from_cache(filters: dict) -> dict:
    """Return all cached profiles, optionally filtered by market cap."""
    cache = load_cache()
    min_cap = filters.get('min_market_cap', 0)
    max_cap = filters.get('max_market_cap', 1e18)
    profiles = {
        t: p for t, p in cache.items()
        if p.get('market_cap') and min_cap <= p['market_cap'] <= max_cap
    }
    return deduplicate_profiles(profiles)


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
