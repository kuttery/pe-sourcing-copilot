"""
fmp_probe.py — one-off FMP API probe (do not import into pipeline).

Usage:  python fmp_probe.py
Probes SMAR (delisted), and if successful also SQSP (delisted) + DDOG (live).
Prints raw API responses and a structured summary of the fields the pipeline needs.
"""
import os
import json
import urllib.request
import urllib.parse

# ── load .env manually (no third-party dotenv) ──────────────────────────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            os.environ[_k.strip()] = _v.strip()

API_KEY = os.environ.get("FMP_API_KEY", "")
BASE = "https://financialmodelingprep.com/api"


def _get(path: str, params: dict = None) -> object:
    p = dict(params or {})
    p["apikey"] = API_KEY
    url = f"{BASE}{path}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}


def probe_ticker(ticker: str) -> dict:
    print(f"\n{'='*60}")
    print(f"  PROBING: {ticker}")
    print(f"{'='*60}")

    # 1. Profile — market cap, EV, description, sector
    profile_raw = _get(f"/v3/profile/{ticker}")
    print(f"\n[1] /v3/profile  →  {len(profile_raw) if isinstance(profile_raw, list) else 'dict/error'} record(s)")
    profile = profile_raw[0] if isinstance(profile_raw, list) and profile_raw else {}
    if "_error" in profile_raw:
        print("    ERROR:", profile_raw)
    else:
        for k in ["companyName", "mktCap", "volAvg", "sector", "industry",
                  "enterpriseValue", "description"]:
            v = profile.get(k)
            snippet = str(v)[:80] if v else "None"
            print(f"    {k:25s}: {snippet}")

    # 2. Income statement — revenue, EBITDA, revenue growth
    inc_raw = _get(f"/v3/income-statement/{ticker}", {"limit": 3})
    print(f"\n[2] /v3/income-statement  →  {len(inc_raw) if isinstance(inc_raw, list) else 'dict/error'} period(s)")
    if isinstance(inc_raw, list) and inc_raw:
        for period in inc_raw[:2]:
            print(f"    date={period.get('date')}  "
                  f"revenue={period.get('revenue')}  "
                  f"ebitda={period.get('ebitda')}  "
                  f"grossProfit={period.get('grossProfit')}")
    else:
        print("    raw:", inc_raw)

    # 3. Balance sheet — total debt, cash
    bs_raw = _get(f"/v3/balance-sheet-statement/{ticker}", {"limit": 2})
    print(f"\n[3] /v3/balance-sheet-statement  →  {len(bs_raw) if isinstance(bs_raw, list) else 'dict/error'} period(s)")
    if isinstance(bs_raw, list) and bs_raw:
        for period in bs_raw[:2]:
            print(f"    date={period.get('date')}  "
                  f"totalDebt={period.get('totalDebt')}  "
                  f"cashAndShortTermInvestments={period.get('cashAndShortTermInvestments')}")
    else:
        print("    raw:", bs_raw)

    # 4. Cash-flow statement — free cash flow
    cf_raw = _get(f"/v3/cash-flow-statement/{ticker}", {"limit": 2})
    print(f"\n[4] /v3/cash-flow-statement  →  {len(cf_raw) if isinstance(cf_raw, list) else 'dict/error'} period(s)")
    if isinstance(cf_raw, list) and cf_raw:
        for period in cf_raw[:2]:
            print(f"    date={period.get('date')}  "
                  f"freeCashFlow={period.get('freeCashFlow')}  "
                  f"operatingCashFlow={period.get('operatingCashFlow')}")
    else:
        print("    raw:", cf_raw)

    # 5. Key metrics — EV/Revenue, net debt, revenue growth (TTM)
    km_raw = _get(f"/v3/key-metrics/{ticker}", {"limit": 2})
    print(f"\n[5] /v3/key-metrics  →  {len(km_raw) if isinstance(km_raw, list) else 'dict/error'} period(s)")
    if isinstance(km_raw, list) and km_raw:
        for period in km_raw[:2]:
            print(f"    date={period.get('date')}  "
                  f"evToSales={period.get('evToSales')}  "
                  f"netDebt={period.get('netDebt')}  "
                  f"revenuePerShare={period.get('revenuePerShare')}")
    else:
        print("    raw:", km_raw)

    # ── structured summary of pipeline-required fields ───────────────────────
    inc = inc_raw[0] if isinstance(inc_raw, list) and inc_raw else {}
    inc_prev = inc_raw[1] if isinstance(inc_raw, list) and len(inc_raw) > 1 else {}
    bs  = bs_raw[0]  if isinstance(bs_raw,  list) and bs_raw  else {}
    cf  = cf_raw[0]  if isinstance(cf_raw,  list) and cf_raw  else {}
    km  = km_raw[0]  if isinstance(km_raw,  list) and km_raw  else {}

    rev      = inc.get("revenue")
    rev_prev = inc_prev.get("revenue")
    ebitda   = inc.get("ebitda")
    fcf      = cf.get("freeCashFlow")
    debt     = bs.get("totalDebt")
    cash     = bs.get("cashAndShortTermInvestments")
    mktcap   = profile.get("mktCap")
    ev       = profile.get("enterpriseValue") or km.get("enterpriseValue")
    ev_rev   = km.get("evToSales")
    net_debt_from_km = km.get("netDebt")

    ebitda_margin = (ebitda / rev) if (ebitda and rev) else None
    fcf_margin    = (fcf / rev)    if (fcf and rev)    else None
    rev_growth    = ((rev - rev_prev) / abs(rev_prev)) if (rev and rev_prev) else None
    net_debt      = net_debt_from_km if net_debt_from_km is not None else (
                    (debt - cash) if (debt is not None and cash is not None) else None)
    net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

    summary = {
        "market_cap":     mktcap,
        "revenue":        rev,
        "ebitda":         ebitda,
        "ebitda_margin":  round(ebitda_margin, 4) if ebitda_margin is not None else None,
        "fcf":            fcf,
        "fcf_margin":     round(fcf_margin, 4) if fcf_margin is not None else None,
        "revenue_growth": round(rev_growth, 4)  if rev_growth  is not None else None,
        "enterprise_value": ev,
        "ev_revenue":     ev_rev,
        "net_debt":       net_debt,
        "net_debt_ebitda": round(net_debt_ebitda, 4) if net_debt_ebitda is not None else None,
    }
    complete = all(v is not None for v in summary.values())

    print(f"\n── PIPELINE FIELDS SUMMARY ({'COMPLETE' if complete else 'INCOMPLETE'}) ──")
    for k, v in summary.items():
        flag = "✓" if v is not None else "✗ MISSING"
        print(f"    {k:20s}: {v}  {flag}")

    return summary


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: FMP_API_KEY not found in .env")
        raise SystemExit(1)
    print(f"FMP key loaded: {API_KEY[:8]}...")

    # Step 1 — probe SMAR (delisted PE target)
    smar = probe_ticker("SMAR")

    smar_complete = all(v is not None for v in smar.values())
    print(f"\n\n{'='*60}")
    print(f"SMAR complete for pipeline: {'YES' if smar_complete else 'NO — see MISSING fields above'}")
    print(f"{'='*60}")

    if smar_complete or any(v is not None for v in smar.values()):
        print("\nSMAR returned some data — probing SQSP (delisted) and DDOG (live) for consistency...\n")
        probe_ticker("SQSP")
        probe_ticker("DDOG")
    else:
        print("\nSMAR returned nothing — FMP free tier likely blocks delisted data.")
        print("Check the raw responses above for error messages.")
