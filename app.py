"""
app.py — PE Sourcing Copilot — reactive financial screener
Run with:  streamlit run app.py
"""
import os, sys, json
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="PE Sourcing Copilot",
    page_icon="🔍",
    layout="wide",
)

# ── load data once at startup ─────────────────────────────────────────────────
@st.cache_data
def load_data():
    cache_path = os.path.join(os.path.dirname(__file__), "data", "cache.json")
    universe_path = os.path.join(os.path.dirname(__file__), "data", "universe.csv")

    with open(cache_path) as f:
        cache = json.load(f)

    universe_df = pd.read_csv(universe_path)
    labels = dict(zip(universe_df["ticker"], universe_df["pe_acquired"]))

    # score in background
    sys.path.insert(0, os.path.dirname(__file__))
    from agents import scoring_agent
    scores = {t: scoring_agent.score_company(p) for t, p in cache.items()}

    rows = []
    for ticker, p in cache.items():
        s = scores.get(ticker, {})
        rows.append({
            "Ticker":         ticker,
            "Company":        p.get("company_name", ticker),
            "Market Cap ($B)": round(p["market_cap"] / 1e9, 2) if p.get("market_cap") else None,
            "Revenue ($M)":   round(p["revenue"] / 1e6, 0) if p.get("revenue") else None,
            "Rev Growth (%)": round(p["revenue_growth"] * 100, 1) if p.get("revenue_growth") is not None else None,
            "EBITDA Margin (%)": round(p["ebitda_margin"] * 100, 1) if p.get("ebitda_margin") is not None else None,
            "FCF Margin (%)": round(p["fcf_margin"] * 100, 1) if p.get("fcf_margin") is not None else None,
            "EV / Revenue":   round(p["ev_revenue"], 1) if p.get("ev_revenue") else None,
            "Net Debt / EBITDA": round(p["net_debt_ebitda"], 1) if p.get("net_debt_ebitda") is not None else None,
            "PE Score":       s.get("pe_score"),
            "PE Acquired":    bool(labels.get(ticker, 0)),
            # raw for filtering
            "_market_cap":    p.get("market_cap"),
            "_rev_growth":    p.get("revenue_growth"),
            "_ebitda_margin": p.get("ebitda_margin"),
            "_fcf_margin":    p.get("fcf_margin"),
            "_ev_revenue":    p.get("ev_revenue"),
            "_net_debt_ebitda": p.get("net_debt_ebitda"),
        })

    return pd.DataFrame(rows)


@st.cache_data
def load_memos():
    outputs = os.path.join(os.path.dirname(__file__), "outputs")
    memos = {}
    for f in os.listdir(outputs):
        if f.startswith("memo_") and f.endswith(".md"):
            ticker = f[5:-3]
            with open(os.path.join(outputs, f)) as fh:
                memos[ticker] = fh.read()
    return memos


df_all = load_data()
memos = load_memos()

# ── sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    # market cap
    mc_min, mc_max = st.slider(
        "Market Cap ($B)", min_value=0.1, max_value=100.0,
        value=(1.0, 60.0), step=0.5
    )

    # revenue growth
    rg_min, rg_max = st.slider(
        "Revenue Growth (%)", min_value=-20, max_value=60,
        value=(-20, 60), step=1
    )

    # ebitda margin
    em_min, em_max = st.slider(
        "EBITDA Margin (%)", min_value=-50, max_value=60,
        value=(-50, 60), step=1
    )

    # fcf margin
    fcf_min, fcf_max = st.slider(
        "FCF Margin (%)", min_value=-30, max_value=50,
        value=(-30, 50), step=1
    )

    # ev/revenue
    evr_max = st.slider("Max EV / Revenue", min_value=1.0, max_value=30.0, value=30.0, step=0.5)

    # net debt / ebitda
    nd_max = st.number_input("Max Net Debt / EBITDA (blank = no limit)", value=None,
                              min_value=0.0, max_value=20.0, step=0.5,
                              placeholder="No limit")

    st.divider()

    # sort
    sort_by = st.selectbox("Sort by", [
        "PE Score", "Market Cap ($B)", "Rev Growth (%)",
        "EBITDA Margin (%)", "FCF Margin (%)", "EV / Revenue", "Net Debt / EBITDA"
    ])
    sort_asc = st.checkbox("Sort ascending", value=False)

    st.divider()
    show_acquired_only = st.checkbox("Show PE-acquired only", value=False)

# ── apply filters ─────────────────────────────────────────────────────────────
df = df_all.copy()

df = df[
    df["_market_cap"].notna() &
    (df["_market_cap"] >= mc_min * 1e9) &
    (df["_market_cap"] <= mc_max * 1e9)
]

df = df[
    df["_rev_growth"].notna() &
    (df["_rev_growth"] * 100 >= rg_min) &
    (df["_rev_growth"] * 100 <= rg_max)
]

df = df[
    df["_ebitda_margin"].notna() &
    (df["_ebitda_margin"] * 100 >= em_min) &
    (df["_ebitda_margin"] * 100 <= em_max)
]

df = df[
    df["_fcf_margin"].notna() &
    (df["_fcf_margin"] * 100 >= fcf_min) &
    (df["_fcf_margin"] * 100 <= fcf_max)
]

df = df[df["_ev_revenue"].notna() & (df["_ev_revenue"] <= evr_max)]

if nd_max is not None:
    df = df[df["_net_debt_ebitda"].notna() & (df["_net_debt_ebitda"] <= nd_max)]

if show_acquired_only:
    df = df[df["PE Acquired"] == True]

df = df.sort_values(sort_by, ascending=sort_asc, na_position="last")

# drop raw filter columns
display_cols = ["Ticker", "Company", "Market Cap ($B)", "Revenue ($M)",
                "Rev Growth (%)", "EBITDA Margin (%)", "FCF Margin (%)",
                "EV / Revenue", "Net Debt / EBITDA", "PE Score", "PE Acquired"]
df_display = df[display_cols].reset_index(drop=True)

# ── main layout ───────────────────────────────────────────────────────────────
st.title("🔍 PE Sourcing Copilot")
st.caption("Agentic AI framework for private-equity deal sourcing — Software sector")

tab1, tab2 = st.tabs(["📊 Company Screener", "📄 Sourcing Memos"])

with tab1:
    st.markdown(f"**{len(df_display)} companies** match current filters")

    def highlight_acquired(row):
        if row["PE Acquired"] == True:
            return ["background-color: #1a472a; color: white"] * len(row)
        return [""] * len(row)

    def color_score(val):
        if not isinstance(val, float):
            return ""
        if val >= 4.5:   return "background-color: #1a6e1a; color: white"
        elif val >= 4.0: return "background-color: #4a9e2a; color: white"
        elif val >= 3.5: return "background-color: #a0c040; color: black"
        elif val >= 3.0: return "background-color: #e0a020; color: black"
        else:            return "background-color: #c04040; color: white"

    styled = (
        df_display.style
        .apply(highlight_acquired, axis=1)
        .map(color_score, subset=["PE Score"])
        .format({
            "Market Cap ($B)": "{:.2f}",
            "Revenue ($M)":    "{:,.0f}",
            "Rev Growth (%)":  "{:.1f}%",
            "EBITDA Margin (%)": "{:.1f}%",
            "FCF Margin (%)":  "{:.1f}%",
            "EV / Revenue":    "{:.1f}x",
            "Net Debt / EBITDA": lambda x: f"{x:.1f}x" if pd.notna(x) else "n/a",
            "PE Score":        "{:.2f}",
        }, na_rep="n/a")
    )

    st.dataframe(styled, use_container_width=True, hide_index=True, height=600)
    st.caption("Green rows = verified PE take-private transactions. PE Score = buyout-fit (1–5, background calc).")

    csv = df_display.to_csv(index=False)
    st.download_button("⬇ Download CSV", csv, "screener_results.csv", "text/csv")

with tab2:
    if not memos:
        st.info("No memos found in outputs/. Run main.py locally to generate them.")
    else:
        ticker_choice = st.selectbox(
            "Select company",
            options=sorted(memos.keys()),
            format_func=lambda t: f"{t} — {df_all[df_all['Ticker']==t]['Company'].values[0] if len(df_all[df_all['Ticker']==t]) else t}"
        )
        st.markdown(memos[ticker_choice])
        st.download_button(
            "⬇ Download memo",
            memos[ticker_choice],
            f"memo_{ticker_choice}.md",
            "text/markdown",
        )
