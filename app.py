"""
app.py — Streamlit UI for the PE Sourcing Copilot.

Run with:  streamlit run app.py
"""
import os, sys, json
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PE Sourcing Copilot",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 PE Sourcing Copilot")
st.caption("Agentic AI framework for private-equity deal sourcing — Software sector")

# ── sidebar: filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pipeline filters")

    sector = st.selectbox("Sector", ["Software", "Technology", "Healthcare"], index=0)

    col1, col2 = st.columns(2)
    min_cap = col1.number_input("Min market cap ($B)", value=1.0, step=0.5, min_value=0.1)
    max_cap = col2.number_input("Max market cap ($B)", value=60.0, step=5.0, min_value=1.0)

    top_k = st.slider("Top-K for memos", min_value=1, max_value=10, value=5)

    use_cache = st.checkbox("Use cached financial data", value=True,
                            help="Uncheck to re-fetch from yfinance (slow, ~2 min)")

    gen_memos = st.checkbox("Generate LLM memos (uses Claude API)", value=True)

    run_btn = st.button("▶  Run pipeline", type="primary", use_container_width=True)

    st.divider()
    st.caption("Pipeline: Universe → Data → Scoring → Ranking → Memos")

# ── helpers ───────────────────────────────────────────────────────────────────
SCORE_COLOR = {5: "🟢", 4: "🟡", 3: "🟠", 2: "🔴", 1: "🔴"}

def score_bar(v):
    filled = round(v)
    return "█" * filled + "░" * (5 - filled) + f"  {v:.2f}"


def run_pipeline(filters, use_cache, gen_memos, top_k):
    from agents import universe_agent, data_agent, scoring_agent, memo_agent
    from config import TOP_K

    status = st.status("Running pipeline…", expanded=True)

    with status:
        st.write("**[1/4] Universe Agent** — filtering candidate universe…")
        universe_df = universe_agent.run(filters)
        st.write(f"→ {len(universe_df)} candidates after static filters")

        st.write("**[2/4] Data Retrieval Agent** — loading financial profiles…")
        profiles = data_agent.run(universe_df, use_cache=use_cache)

        # market-cap filter
        min_mc = filters.get("min_market_cap", 0)
        max_mc = filters.get("max_market_cap", 1e18)
        profiles = {t: p for t, p in profiles.items()
                    if p.get("market_cap") and min_mc <= p["market_cap"] <= max_mc}
        st.write(f"→ {len(profiles)} profiles after market-cap filter")

        st.write("**[3/4] PE Scoring Agent** — computing buyout-fit scores…")
        scores = scoring_agent.run(profiles)

        ranked = sorted(scores.values(), key=lambda x: x["pe_score"], reverse=True)
        top_tickers = [r["ticker"] for r in ranked[:top_k]]
        st.write(f"→ top-{top_k} tickers: {', '.join(top_tickers)}")

        memos = {}
        if gen_memos:
            st.write("**[4/4] Memo Agent** — generating sourcing memos…")
            memos = memo_agent.run(profiles, scores, top_tickers)
        else:
            st.write("**[4/4] Memo Agent** — skipped (checkbox unchecked)")

        status.update(label="Pipeline complete ✓", state="complete", expanded=False)

    return universe_df, profiles, scores, ranked, memos


# ── main area ─────────────────────────────────────────────────────────────────
if run_btn:
    filters = {
        "sector": sector,
        "geography": None,
        "min_market_cap": min_cap * 1e9,
        "max_market_cap": max_cap * 1e9,
    }

    universe_df, profiles, scores, ranked, memos = run_pipeline(
        filters, use_cache, gen_memos, top_k
    )

    # store in session state so tabs render after button press
    st.session_state["ranked"] = ranked
    st.session_state["profiles"] = profiles
    st.session_state["memos"] = memos
    st.session_state["universe_df"] = universe_df

# render results from session state (persists across re-renders)
if "ranked" in st.session_state:
    ranked = st.session_state["ranked"]
    profiles = st.session_state["profiles"]
    memos = st.session_state["memos"]
    universe_df = st.session_state["universe_df"]

    tab1, tab2, tab3 = st.tabs(["📊 Ranked Shortlist", "📄 Sourcing Memos", "📈 Score Breakdown"])

    # ── tab 1: ranked shortlist ──────────────────────────────────────────────
    with tab1:
        st.subheader("Ranked shortlist — buyout-fit scores")

        # load ground truth labels
        universe_labels = dict(zip(universe_df["ticker"], universe_df["pe_acquired"]))

        rows = []
        for i, r in enumerate(ranked, 1):
            t = r["ticker"]
            acquired = universe_labels.get(t, 0)
            rows.append({
                "Rank": i,
                "Ticker": t,
                "Company": r["company_name"],
                "PE Score": r["pe_score"],
                "Score Bar": score_bar(r["pe_score"]),
                "PE Acquired ✓": "✓" if acquired else "",
                "Scale": r["subscores"].get("scale_fit", "—"),
                "Valuation": r["subscores"].get("valuation_attractiveness", "—"),
                "Cash Flow": r["subscores"].get("cash_flow_stability", "—"),
                "Headroom": r["subscores"].get("improvement_headroom", "—"),
                "Growth": r["subscores"].get("growth_moderation", "—"),
                "Leverage": r["subscores"].get("leverage_capacity", "—"),
            })

        df_out = pd.DataFrame(rows)

        # highlight PE-acquired rows
        def highlight_acquired(row):
            if row["PE Acquired ✓"] == "✓":
                return ["background-color: #1a472a; color: white"] * len(row)
            return [""] * len(row)

        styled = (
            df_out.style
            .apply(highlight_acquired, axis=1)
            .background_gradient(subset=["PE Score"], cmap="RdYlGn", vmin=1, vmax=5)
            .format({"PE Score": "{:.2f}"})
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption("Green rows = verified PE-acquired companies. Score bar filled out of 5.")

        csv = df_out.to_csv(index=False)
        st.download_button("⬇ Download CSV", csv, "ranked_shortlist.csv", "text/csv")

    # ── tab 2: memos ────────────────────────────────────────────────────────
    with tab2:
        if not memos:
            st.info("No memos generated. Enable 'Generate LLM memos' and re-run.")
        else:
            ticker_choice = st.selectbox(
                "Select company",
                options=list(memos.keys()),
                format_func=lambda t: f"{t} — {profiles[t].get('company_name', t)}"
            )
            st.markdown(memos[ticker_choice])
            st.download_button(
                "⬇ Download memo",
                memos[ticker_choice],
                f"memo_{ticker_choice}.md",
                "text/markdown",
            )

    # ── tab 3: score breakdown ───────────────────────────────────────────────
    with tab3:
        st.subheader("Subscore detail")
        ticker_choice2 = st.selectbox(
            "Select company",
            options=[r["ticker"] for r in ranked],
            format_func=lambda t: f"{t} — {profiles[t].get('company_name', t)}",
            key="breakdown_picker",
        )

        r = next(x for x in ranked if x["ticker"] == ticker_choice2)
        p = profiles[ticker_choice2]

        c1, c2, c3 = st.columns(3)
        c1.metric("PE Score", f"{r['pe_score']:.2f} / 5")
        c2.metric("Market Cap", f"${p.get('market_cap', 0)/1e9:.1f}B" if p.get("market_cap") else "n/a")
        c3.metric("EV/Revenue", f"{p.get('ev_revenue', 0):.1f}x" if p.get("ev_revenue") else "n/a")

        st.divider()

        subscore_labels = {
            "scale_fit": "Scale Fit",
            "valuation_attractiveness": "Valuation Attractiveness",
            "cash_flow_stability": "Cash Flow Stability",
            "improvement_headroom": "Improvement Headroom",
            "growth_moderation": "Growth Moderation",
            "leverage_capacity": "Leverage Capacity",
        }

        for key, label in subscore_labels.items():
            score_val = r["subscores"].get(key)
            rationale = r["rationales"].get(key, "")
            if score_val is not None:
                emoji = SCORE_COLOR.get(score_val, "⚪")
                st.markdown(f"**{label}** &nbsp; {emoji} {score_val}/5 &nbsp; — &nbsp; *{rationale}*")
                st.progress(score_val / 5)
            else:
                st.markdown(f"**{label}** &nbsp; ⚪ n/a — *{rationale}*")

        st.divider()
        st.subheader("Raw financials")
        fin_cols = {
            "Revenue": p.get("revenue"), "EBITDA margin": p.get("ebitda_margin"),
            "FCF margin": p.get("fcf_margin"), "Revenue growth": p.get("revenue_growth"),
            "Net debt/EBITDA": p.get("net_debt_ebitda"), "EV/Revenue": p.get("ev_revenue"),
        }
        fin_rows = []
        for k, v in fin_cols.items():
            if v is None:
                fin_rows.append({"Metric": k, "Value": "n/a"})
            elif k in ("Revenue",):
                fin_rows.append({"Metric": k, "Value": f"${v/1e6:,.0f}M"})
            elif k in ("EBITDA margin", "FCF margin", "Revenue growth"):
                fin_rows.append({"Metric": k, "Value": f"{v*100:.1f}%"})
            else:
                fin_rows.append({"Metric": k, "Value": f"{v:.2f}x"})
        st.dataframe(pd.DataFrame(fin_rows), hide_index=True, use_container_width=False)

else:
    st.info("Set your filters in the sidebar and click **▶ Run pipeline** to start.")

    with st.expander("How it works"):
        st.markdown("""
**Five-agent sequential pipeline:**

1. **Universe Agent** — filters `data/universe.csv` by sector / geography
2. **Data Retrieval Agent** — fetches financial profiles from yfinance (cached to disk)
3. **PE Scoring Agent** — scores each company 1–5 on six buyout-fit dimensions
   (scale fit, valuation, cash flow, improvement headroom, growth moderation, leverage)
4. **Coordinator** — ranks by weighted score, selects top-K
5. **Memo Agent** — calls Claude to write a structured sourcing memo for each top-K company

**Design principle:** scoring is fully deterministic and auditable. The LLM is used only
to write narrative memos, never to assign scores.
        """)
