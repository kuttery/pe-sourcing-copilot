"""
data/make_dev_fixture.py

Generates data/cache.json as a DEVELOPMENT FIXTURE so the pipeline can be
tested without internet access to Yahoo Finance.

=============================================================================
IMPORTANT — READ BEFORE USING IN A REAL SUBMISSION
=============================================================================
The numbers below are REALISTIC APPROXIMATIONS of recent public financials,
hand-assembled for pipeline testing. They are NOT a live API pull.

A few anchors are taken from verified FY2025 reporting (e.g. Datadog revenue
~$3.43B and FCF margin ~27%; CrowdStrike revenue ~$3.95B). The remainder are
calibrated estimates of the right order of magnitude.

For your actual capstone submission:
    1. delete data/cache.json
    2. run  `python main.py`  on a machine with internet
    3. the Data Retrieval Agent will repopulate cache.json from LIVE yfinance

This fixture exists ONLY so the system can be demonstrated end-to-end in an
offline sandbox. The report should describe the live yfinance pipeline.
=============================================================================
"""
import json
import os

# ticker: (market_cap, revenue, ebitda_margin, fcf_margin, revenue_growth,
#          net_debt_ebitda, ev_revenue, industry)
# Values in USD. Approximations for development/testing only.
FIXTURE = {
    # --- verified PE take-private positives ---
    "SMAR":  (8.4e9,  1.12e9, 0.10, 0.16, 0.17, 0.5, 7.0,  "Software—Application"),
    "SQSP":  (7.2e9,  1.20e9, 0.16, 0.20, 0.18, 1.8, 5.8,  "Software—Application"),
    "INST":  (4.8e9,  0.57e9, 0.32, 0.22, 0.14, 4.5, 8.0,  "Software—Application"),
    "EVBG":  (1.8e9,  0.45e9, 0.15, 0.12, 0.06, 3.8, 4.0,  "Software—Application"),
    "PWSC":  (5.6e9,  0.74e9, 0.28, 0.18, 0.13, 4.2, 7.2,  "Software—Application"),
    "AYX":   (4.4e9,  1.05e9, 0.14, 0.10, 0.08, 3.5, 4.2,  "Software—Application"),
    "MODN":  (1.25e9, 0.25e9, 0.18, 0.13, 0.07, 1.2, 4.8,  "Software—Application"),
    "DAY":   (10.0e9, 1.76e9, 0.20, 0.12, 0.16, 2.2, 5.5,  "Software—Application"),
    "OLO":   (2.0e9,  0.29e9, 0.08, 0.10, 0.21, 0.2, 6.5,  "Software—Application"),
    "PRO":   (1.4e9,  0.34e9, 0.10, 0.09, 0.08, 1.8, 4.0,  "Software—Application"),
    "JAMF":  (2.2e9,  0.66e9, 0.16, 0.18, 0.10, 2.0, 3.3,  "Software—Application"),
    "NVEI":  (6.15e9, 1.30e9, 0.36, 0.22, 0.20, 3.0, 4.6,  "Software—Infrastructure"),
    "CTLT":  (16.3e9, 4.40e9, 0.18, 0.06, 0.04, 4.0, 3.7,  "Drug Manufacturers"),
    "WBA":   (23.7e9, 147e9,  0.03, 0.02, 0.01, 5.5, 0.3,  "Pharmaceutical Retailers"),
    # --- still-public negatives ---
    "DDOG":  (48e9,   3.43e9, 0.21, 0.27, 0.28, -1.0, 11.4, "Software—Application"),
    "SNOW":  (62e9,   3.80e9, 0.06, 0.24, 0.29, -1.2, 14.0, "Software—Application"),
    "NET":   (38e9,   1.90e9, 0.10, 0.12, 0.28, 0.3, 18.0, "Software—Infrastructure"),
    "HUBS":  (28e9,   2.80e9, 0.16, 0.16, 0.20, -0.5, 9.5, "Software—Application"),
    "WDAY":  (62e9,   8.40e9, 0.25, 0.30, 0.16, -0.3, 7.2, "Software—Application"),
    "TEAM":  (45e9,   4.80e9, 0.22, 0.27, 0.21, 0.1, 9.0,  "Software—Application"),
    "NOW":   (180e9,  11.0e9, 0.30, 0.31, 0.22, -0.4, 16.0,"Software—Application"),
    "CRM":   (260e9,  38.0e9, 0.33, 0.30, 0.09, 0.6, 6.8,  "Software—Application"),
    "ZM":    (22e9,   4.70e9, 0.40, 0.34, 0.03, -2.5, 4.5, "Software—Application"),
    "DOCU":  (16e9,   2.98e9, 0.28, 0.30, 0.08, -1.0, 5.2, "Software—Application"),
    "TWLO":  (16e9,   4.46e9, 0.12, 0.16, 0.09, -0.8, 3.5, "Software—Infrastructure"),
    "OKTA":  (15e9,   2.61e9, 0.20, 0.27, 0.13, -0.6, 5.6, "Software—Infrastructure"),
    "ZS":    (32e9,   2.50e9, 0.22, 0.26, 0.27, 0.2, 12.5, "Software—Infrastructure"),
    "CRWD":  (95e9,   3.95e9, 0.22, 0.27, 0.29, -0.7, 22.0,"Software—Infrastructure"),
    "PANW":  (130e9,  8.80e9, 0.27, 0.35, 0.15, -0.2, 14.0,"Software—Infrastructure"),
    "MDB":   (20e9,   2.00e9, 0.10, 0.14, 0.20, -0.9, 9.5, "Software—Infrastructure"),
    "ESTC":  (10e9,   1.48e9, 0.13, 0.16, 0.18, 0.1, 6.5,  "Software—Infrastructure"),
    "PD":    (1.6e9,  0.47e9, 0.12, 0.14, 0.08, 1.0, 3.2,  "Software—Application"),
    "FROG":  (3.8e9,  0.43e9, 0.13, 0.18, 0.22, -1.5, 8.5, "Software—Infrastructure"),
    "BILL":  (5.0e9,  1.45e9, 0.16, 0.20, 0.14, -0.6, 3.4, "Software—Application"),
    "PCTY":  (10e9,   1.55e9, 0.30, 0.24, 0.15, -1.0, 6.2, "Software—Application"),
    "PAYC":  (12e9,   1.95e9, 0.40, 0.28, 0.11, -1.2, 6.0, "Software—Application"),
    "APPF":  (8e9,    0.83e9, 0.24, 0.22, 0.20, -0.8, 9.0, "Software—Application"),
    "BLKB":  (3.5e9,  1.16e9, 0.22, 0.18, 0.05, 3.0, 3.2,  "Software—Application"),
    "ALRM":  (3.0e9,  0.94e9, 0.16, 0.14, 0.08, 0.5, 3.0,  "Software—Application"),
    "WK":    (5.0e9,  0.74e9, 0.10, 0.12, 0.18, -0.5, 6.8, "Software—Application"),
}

NAMES = {
    "SMAR": "Smartsheet", "SQSP": "Squarespace", "INST": "Instructure",
    "EVBG": "Everbridge", "PWSC": "PowerSchool", "AYX": "Alteryx",
    "MODN": "Model N", "DAY": "Dayforce", "OLO": "Olo", "PRO": "PROS Holdings",
    "JAMF": "Jamf Holding", "NVEI": "Nuvei", "CTLT": "Catalent",
    "WBA": "Walgreens Boots Alliance", "DDOG": "Datadog", "SNOW": "Snowflake",
    "NET": "Cloudflare", "HUBS": "HubSpot", "WDAY": "Workday",
    "TEAM": "Atlassian", "NOW": "ServiceNow", "CRM": "Salesforce",
    "ZM": "Zoom Communications", "DOCU": "DocuSign", "TWLO": "Twilio",
    "OKTA": "Okta", "ZS": "Zscaler", "CRWD": "CrowdStrike",
    "PANW": "Palo Alto Networks", "MDB": "MongoDB", "ESTC": "Elastic",
    "PD": "PagerDuty", "FROG": "JFrog", "BILL": "BILL Holdings",
    "PCTY": "Paylocity", "PAYC": "Paycom Software", "APPF": "AppFolio",
    "BLKB": "Blackbaud", "ALRM": "Alarm.com", "WK": "Workiva",
}


def build():
    cache = {}
    for ticker, vals in FIXTURE.items():
        mc, rev, ebm, fcfm, growth, nde, evr, industry = vals
        cache[ticker] = {
            "ticker": ticker,
            "company_name": NAMES.get(ticker, ticker),
            "description": f"{NAMES.get(ticker, ticker)} is a company in the "
                           f"{industry} space. (Development-fixture description; "
                           f"a live run pulls the real business summary from yfinance.)",
            "industry": industry,
            "sector_yf": "Technology",
            "market_cap": mc,
            "revenue": rev,
            "ebitda": ebm * rev,
            "ebitda_margin": ebm,
            "fcf": fcfm * rev,
            "fcf_margin": fcfm,
            "revenue_growth": growth,
            "total_debt": None,
            "cash": None,
            "net_debt": nde * (ebm * rev),
            "net_debt_ebitda": nde,
            "enterprise_value": evr * rev,
            "ev_revenue": evr,
            "data_complete": True,
            "_dev_fixture": True,  # marker: this is NOT live data
        }
    return cache


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "cache.json")
    with open(out_path, "w") as f:
        json.dump(build(), f, indent=2)
    print(f"Wrote development fixture: {out_path} ({len(FIXTURE)} companies)")
    print("NOTE: delete this file and run main.py with internet for live data.")
