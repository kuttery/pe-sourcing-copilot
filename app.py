"""
app.py — PE Sourcing Copilot
Run with:  streamlit run app.py
"""
import os, sys, json
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(page_title="PE Sourcing Copilot", page_icon="🔍", layout="wide")

from agents import universe_agent, scoring_agent
from agents.universe_agent import REGION_LABELS, ALL_SECTORS

# ── helpers ───────────────────────────────────────────────────────────────────

def profiles_to_df(profiles: dict) -> pd.DataFrame:
    from agents import scoring_agent
    rows = []
    for ticker, p in profiles.items():
        s = scoring_agent.score_company(p)
        rows.append({
            "Ticker":              ticker,
            "Company":             p.get("company_name", ticker),
            "Country":             p.get("country") or "—",
            "Sector":              p.get("sector_yf") or "—",
            "Industry":            p.get("industry") or "—",
            "Market Cap ($B)":     round(p["market_cap"] / 1e9, 2) if p.get("market_cap") else None,
            "Revenue ($M)":        round(p["revenue"] / 1e6, 0)    if p.get("revenue")     else None,
            "Rev Growth (%)":      round(p["revenue_growth"] * 100, 1) if p.get("revenue_growth") is not None else None,
            "EBITDA Margin (%)":   round(p["ebitda_margin"] * 100, 1)  if p.get("ebitda_margin")  is not None else None,
            "FCF Margin (%)":      round(p["fcf_margin"] * 100, 1)     if p.get("fcf_margin")     is not None else None,
            "EV / Revenue":        round(p["ev_revenue"], 1)            if p.get("ev_revenue")              else None,
            "Net Debt / EBITDA":   round(p["net_debt_ebitda"], 1)       if p.get("net_debt_ebitda") is not None else None,
            "PE Score":            s.get("pe_score"),
            "_market_cap":         p.get("market_cap"),
            "_rev_growth":         p.get("revenue_growth"),
            "_ebitda_margin":      p.get("ebitda_margin"),
            "_fcf_margin":         p.get("fcf_margin"),
            "_ev_revenue":         p.get("ev_revenue"),
            "_net_debt_ebitda":    p.get("net_debt_ebitda"),
            "_country":            p.get("country") or "",
            "_industry":           p.get("industry") or "",
            "_sector":             p.get("sector_yf") or "",
        })
    return pd.DataFrame(rows)


def apply_filters(df, rg_min, rg_max, em_min, em_max, fcf_min, fcf_max,
                  evr_max, nd_max, countries, industries):
    df = df[df["_rev_growth"].notna() & (df["_rev_growth"]*100 >= rg_min) & (df["_rev_growth"]*100 <= rg_max)]
    df = df[df["_ebitda_margin"].notna() & (df["_ebitda_margin"]*100 >= em_min) & (df["_ebitda_margin"]*100 <= em_max)]
    df = df[df["_fcf_margin"].notna() & (df["_fcf_margin"]*100 >= fcf_min) & (df["_fcf_margin"]*100 <= fcf_max)]
    df = df[df["_ev_revenue"].notna() & (df["_ev_revenue"] <= evr_max)]
    if nd_max is not None:
        df = df[df["_net_debt_ebitda"].notna() & (df["_net_debt_ebitda"] <= nd_max)]
    if countries:
        df = df[df["_country"].isin(countries)]
    if industries:
        df = df[df["_industry"].isin(industries)]
    return df


def render_table(df_display, sort_by, sort_asc):
    df_display = df_display.sort_values(sort_by, ascending=sort_asc, na_position="last")

    display_cols = ["Ticker", "Company", "Country", "Industry",
                    "Market Cap ($B)", "Revenue ($M)",
                    "Rev Growth (%)", "EBITDA Margin (%)", "FCF Margin (%)",
                    "EV / Revenue", "Net Debt / EBITDA", "PE Score"]
    df_show = df_display[display_cols].reset_index(drop=True)

    def color_score(val):
        if not isinstance(val, float): return ""
        if val >= 4.5:   return "background-color: #1a6e1a; color: white"
        elif val >= 4.0: return "background-color: #4a9e2a; color: white"
        elif val >= 3.5: return "background-color: #a0c040; color: black"
        elif val >= 3.0: return "background-color: #e0a020; color: black"
        else:            return "background-color: #c04040; color: white"

    styled = (
        df_show.style
        .map(color_score, subset=["PE Score"])
        .format({
            "Market Cap ($B)":   "{:.2f}",
            "Revenue ($M)":      "{:,.0f}",
            "Rev Growth (%)":    "{:.1f}%",
            "EBITDA Margin (%)": "{:.1f}%",
            "FCF Margin (%)":    "{:.1f}%",
            "EV / Revenue":      "{:.1f}x",
            "Net Debt / EBITDA": lambda x: f"{x:.1f}x" if pd.notna(x) else "n/a",
            "PE Score":          "{:.2f}",
        }, na_rep="n/a")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=600)
    st.caption(f"PE Score = buyout-fit 1–5 (background calc). {len(df_show)} companies shown.")
    csv = df_show.to_csv(index=False)
    st.download_button("⬇ Download CSV", csv, "screener_results.csv", "text/csv")


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Market filters")

    # Geography
    region_options = {v: k for k, v in REGION_LABELS.items()}  # label -> code
    selected_countries = st.multiselect(
        "Countries / Regions",
        options=sorted(REGION_LABELS.values()),
        default=["United States"],
        help="Used when fetching live data. Filters cached results by country."
    )
    selected_region_codes = [region_options[c] for c in selected_countries if c in region_options]

    # Sector
    selected_sectors = st.multiselect(
        "Sectors",
        options=ALL_SECTORS,
        default=["Technology"],
        help="Used when fetching live data from Yahoo Finance screener."
    )

    # Market cap
    mc_min, mc_max = st.slider("Market Cap ($B)", 0.1, 500.0, (1.0, 60.0), step=0.5)

    st.divider()
    st.subheader("Fundamentals")

    rg_min, rg_max   = st.slider("Revenue Growth (%)",  -20, 100, (-20, 100), step=1)
    em_min, em_max   = st.slider("EBITDA Margin (%)",   -50,  80,  (-50,  80), step=1)
    fcf_min, fcf_max = st.slider("FCF Margin (%)",      -30,  60,  (-30,  60), step=1)
    evr_max  = st.slider("Max EV / Revenue", 1.0, 50.0, 50.0, step=0.5)
    nd_max   = st.number_input("Max Net Debt / EBITDA", value=None,
                                min_value=0.0, max_value=20.0, step=0.5,
                                placeholder="No limit")

    # Industry filter — built from cached data
    cache_now = universe_agent.load_cache()
    all_industries = sorted({p.get("industry","") for p in cache_now.values() if p.get("industry")})
    selected_industries = st.multiselect("Industry (from cache)", options=all_industries,
                                          default=[], placeholder="All industries")

    st.divider()
    sort_by  = st.selectbox("Sort by", ["PE Score", "Market Cap ($B)", "Rev Growth (%)",
                                         "EBITDA Margin (%)", "FCF Margin (%)",
                                         "EV / Revenue", "Net Debt / EBITDA"])
    sort_asc = st.checkbox("Sort ascending", value=False)

    st.divider()
    st.subheader("Data source")
    st.caption(f"Cached: {len(cache_now)} companies")
    fetch_btn = st.button("🔄 Fetch from market", type="primary", use_container_width=True,
                           help="Query Yahoo screener with selected countries + sectors, fetch fresh fundamentals")
    st.caption("Filters apply to cached data instantly. Click Fetch to pull new companies from Yahoo Finance.")


# ── main ──────────────────────────────────────────────────────────────────────
st.title("🔍 PE Sourcing Copilot")
st.caption("Live US software company screener — powered by Yahoo Finance")

tab1, tab2 = st.tabs(["📊 Screener", "📄 Sourcing Memos"])

with tab1:

    if fetch_btn:
        filters = {
            "min_market_cap": mc_min * 1e9,
            "max_market_cap": mc_max * 1e9,
            "regions":  selected_region_codes or ['us'],
            "sectors":  selected_sectors or ['Technology'],
        }

        progress_bar = st.progress(0, text="Querying Yahoo Finance screener...")
        status_text  = st.empty()

        def on_progress(done, total, ticker):
            if total == 0: return
            pct = done / total
            label = f"Fetching {ticker} ... ({done}/{total})" if ticker != "done" else "Done!"
            progress_bar.progress(pct, text=label)
            status_text.caption(label)

        profiles = universe_agent.run_live(filters, progress_cb=on_progress)
        progress_bar.empty()
        status_text.empty()
        st.session_state["profiles_df"] = profiles_to_df(profiles)
        st.success(f"Fetched {len(profiles)} software companies from Yahoo Finance.")

    # load from cache if no live fetch yet
    if "profiles_df" not in st.session_state:
        filters = {"min_market_cap": 0, "max_market_cap": 1e18}
        profiles = universe_agent.run_from_cache(filters)
        if profiles:
            st.session_state["profiles_df"] = profiles_to_df(profiles)

    if "profiles_df" in st.session_state:
        df_all = st.session_state["profiles_df"]

        # apply market cap filter
        df = df_all[
            df_all["_market_cap"].notna() &
            (df_all["_market_cap"] >= mc_min * 1e9) &
            (df_all["_market_cap"] <= mc_max * 1e9)
        ].copy()

        # apply fundamental filters
        # country filter from multiselect
        country_filter = selected_countries if selected_countries else []
        df = apply_filters(df, rg_min, rg_max, em_min, em_max, fcf_min, fcf_max,
                           evr_max, nd_max, country_filter, selected_industries)

        st.markdown(f"**{len(df)} companies** match current filters (from {len(df_all)} cached)")
        render_table(df, sort_by, sort_asc)
    else:
        st.info("No cached data yet. Click **🔄 Fetch from market** in the sidebar to pull live data from Yahoo Finance.")

with tab2:
    outputs = os.path.join(os.path.dirname(__file__), "outputs")
    memos = {}
    for fname in os.listdir(outputs):
        if fname.startswith("memo_") and fname.endswith(".md"):
            ticker = fname[5:-3]
            with open(os.path.join(outputs, fname)) as fh:
                memos[ticker] = fh.read()

    if not memos:
        st.info("No memos yet. Run `python main.py` locally to generate sourcing memos for the top companies.")
    else:
        cache = universe_agent.load_cache()
        ticker_choice = st.selectbox(
            "Select company",
            options=sorted(memos.keys()),
            format_func=lambda t: f"{t} — {cache[t]['company_name'] if t in cache else t}"
        )
        st.markdown(memos[ticker_choice])
        st.download_button("⬇ Download memo", memos[ticker_choice],
                           f"memo_{ticker_choice}.md", "text/markdown")
