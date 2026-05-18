"""
app.py — PE Sourcing Copilot
Run with:  streamlit run app.py
"""
import os, sys, json
import pandas as pd
import altair as alt
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(page_title="PE Sourcing Copilot", layout="wide")

from pe_style import (load_css, score_badge, deal_card_open, deal_card_close,
                      filter_count, section, CHART_COLORS)
load_css("styles.css")

from agents import universe_agent, scoring_agent
from agents.universe_agent import REGION_LABELS, ALL_SECTORS


# ── helpers ───────────────────────────────────────────────────────────────────

def profiles_to_df(profiles: dict) -> pd.DataFrame:
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
    df = df[df["_rev_growth"].notna()   & (df["_rev_growth"]*100   >= rg_min)  & (df["_rev_growth"]*100   <= rg_max)]
    df = df[df["_ebitda_margin"].notna() & (df["_ebitda_margin"]*100 >= em_min) & (df["_ebitda_margin"]*100 <= em_max)]
    df = df[df["_fcf_margin"].notna()   & (df["_fcf_margin"]*100   >= fcf_min) & (df["_fcf_margin"]*100   <= fcf_max)]
    df = df[df["_ev_revenue"].notna()   & (df["_ev_revenue"] <= evr_max)]
    if nd_max is not None:
        df = df[df["_net_debt_ebitda"].notna() & (df["_net_debt_ebitda"] <= nd_max)]
    if countries and "_country" in df.columns:
        df = df[df["_country"].isin(countries)]
    if industries and "_industry" in df.columns:
        df = df[df["_industry"].isin(industries)]
    return df


def render_table(df_display, sort_by, sort_asc):
    df_display = df_display.sort_values(sort_by, ascending=sort_asc, na_position="last")

    display_cols = ["Ticker", "Company", "Country", "Industry",
                    "Market Cap ($B)", "Revenue ($M)",
                    "Rev Growth (%)", "EBITDA Margin (%)", "FCF Margin (%)",
                    "EV / Revenue", "Net Debt / EBITDA", "PE Score"]
    display_cols = [c for c in display_cols if c in df_display.columns]
    df_show = df_display[display_cols].reset_index(drop=True)

    def color_score(val):
        if not isinstance(val, (int, float)):
            return ""
        if val >= 4.5:   return "background-color: #1F7A4D; color: white"
        elif val >= 4.0: return "background-color: #1B2A4A; color: white"
        elif val >= 3.5: return "background-color: #2C4170; color: white"
        elif val >= 3.0: return "background-color: #B8954A; color: black"
        else:            return "background-color: #C2410C; color: white"

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
    st.dataframe(styled, use_container_width=True, hide_index=True, height=560)
    csv = df_show.to_csv(index=False)
    st.download_button("Download CSV", csv, "screener_results.csv", "text/csv")


def render_charts(df):
    score_col, scatter_col = st.columns(2)

    with score_col:
        st.markdown("**Score distribution**")
        scores = df["PE Score"].dropna()
        if len(scores):
            bins   = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.01]
            labels = ["1.0–1.5", "1.5–2.0", "2.0–2.5", "2.5–3.0",
                      "3.0–3.5", "3.5–4.0", "4.0–4.5", "4.5–5.0"]
            binned = pd.cut(scores, bins=bins, labels=labels, right=False)
            dist   = (binned.value_counts()
                            .reindex(labels, fill_value=0)
                            .reset_index())
            dist.columns = ["Range", "Count"]
            chart = (
                alt.Chart(dist)
                .mark_bar(color=CHART_COLORS["primary"],
                          cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                .encode(
                    x=alt.X("Range:O", sort=None, title="PE Score",
                             axis=alt.Axis(labelColor=CHART_COLORS["axis_text"],
                                           domainColor=CHART_COLORS["grid"],
                                           tickColor=CHART_COLORS["grid"])),
                    y=alt.Y("Count:Q", title="Companies",
                             axis=alt.Axis(labelColor=CHART_COLORS["axis_text"],
                                           gridColor=CHART_COLORS["grid"])),
                    tooltip=["Range", "Count"],
                )
                .properties(height=220, background=CHART_COLORS["bg"])
                .configure_view(strokeOpacity=0)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No score data.")

    with scatter_col:
        st.markdown("**Valuation vs PE Score**")
        sc_df = (df[["Ticker", "Company", "PE Score", "EV / Revenue", "Market Cap ($B)"]]
                 .dropna())
        if len(sc_df):
            scatter = (
                alt.Chart(sc_df)
                .mark_circle(opacity=0.75)
                .encode(
                    x=alt.X("PE Score:Q",
                             scale=alt.Scale(domain=[1, 5.2]),
                             title="PE Score",
                             axis=alt.Axis(labelColor=CHART_COLORS["axis_text"],
                                           gridColor=CHART_COLORS["grid"])),
                    y=alt.Y("EV / Revenue:Q",
                             title="EV / Revenue (x)",
                             axis=alt.Axis(labelColor=CHART_COLORS["axis_text"],
                                           gridColor=CHART_COLORS["grid"])),
                    size=alt.Size("Market Cap ($B):Q",
                                  scale=alt.Scale(range=[40, 400]),
                                  legend=None),
                    color=alt.value(CHART_COLORS["primary"]),
                    tooltip=["Ticker", "Company", "PE Score",
                              "EV / Revenue", "Market Cap ($B)"],
                )
                .properties(height=220, background=CHART_COLORS["bg"])
                .configure_view(strokeOpacity=0)
            )
            st.altair_chart(scatter, use_container_width=True)
        else:
            st.info("No valuation data.")


def render_deal_card(ticker: str, df: pd.DataFrame, profiles: dict):
    """Render the full deal card for one company as a single HTML block."""
    if ticker not in profiles:
        st.warning("Profile not available — try refreshing from market.")
        return

    p  = profiles[ticker]
    sc = scoring_agent.score_company(p)

    company  = p.get("company_name", ticker)
    industry = p.get("industry") or "—"
    country  = p.get("country")  or "—"
    subtitle = f"{industry} · {country}"
    pe       = sc.get("pe_score", 0)
    ss       = sc.get("subscores", {})
    rt       = sc.get("rationales", {})

    # Subscore table rows
    dim_labels = {
        "scale_fit":         "Scale Fit",
        "valuation":         "Valuation",
        "cash_generation":   "Cash Generation",
        "margin_headroom":   "Margin Headroom",
        "growth_quality":    "Growth Quality",
        "leverage_capacity": "Leverage Capacity",
    }
    sub_rows = ""
    for key, label in dim_labels.items():
        val   = ss.get(key)
        rat   = rt.get(key, "—")
        badge = (score_badge(val) if val is not None
                 else '<span class="pe-score pe-score-low">n/a</span>')
        sub_rows += (
            f"<tr>"
            f"<td style='padding:4px 8px;color:#6B7280;font-size:0.82rem;'>{label}</td>"
            f"<td style='padding:4px 8px;text-align:center;'>{badge}</td>"
            f"<td style='padding:4px 8px;font-size:0.82rem;color:#1B2A4A;'>{rat}</td>"
            f"</tr>"
        )

    def _m(v):
        if v is None: return "—"
        if abs(v) >= 1e9: return f"${v/1e9:.1f}B"
        if abs(v) >= 1e6: return f"${v/1e6:.0f}M"
        return f"${v:,.0f}"

    def _pct(v): return f"{v*100:.1f}%" if v is not None else "—"
    def _x(v):   return f"{v:.1f}x"     if v is not None else "—"

    desc = p.get("description") or ""
    if len(desc) > 380:
        desc = desc[:377] + "…"

    kpis = [
        ("Market Cap",       _m(p.get("market_cap"))),
        ("Revenue",          _m(p.get("revenue"))),
        ("Enterprise Value", _m(p.get("enterprise_value"))),
        ("EV / Revenue",     _x(p.get("ev_revenue"))),
        ("Rev Growth",       _pct(p.get("revenue_growth"))),
        ("EBITDA Margin",    _pct(p.get("ebitda_margin"))),
        ("Gross Margin",     _pct(p.get("gross_margin"))),
        ("FCF Margin",       _pct(p.get("fcf_margin"))),
        ("Net Debt / EBITDA", _x(p.get("net_debt_ebitda"))),
    ]
    kpi_cells = "".join(
        f"<div style='background:#F5F6F8;border-radius:8px;padding:0.6rem 0.8rem;'>"
        f"<div style='font-size:0.72rem;color:#6B7280;text-transform:uppercase;"
        f"letter-spacing:0.04em;'>{lbl}</div>"
        f"<div style='font-weight:700;color:#1B2A4A;'>{val}</div></div>"
        for lbl, val in kpis
    )

    html = f"""
<div class="pe-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div class="pe-card-title">{company}</div>
      <div class="pe-card-subtitle">{subtitle}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:0.75rem;color:#6B7280;text-transform:uppercase;
                  letter-spacing:0.05em;margin-bottom:0.2rem;">PE Score</div>
      {score_badge(pe, is_top=(pe >= 4.5))}
    </div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);
              gap:0.6rem;margin:0.9rem 0;">
    {kpi_cells}
  </div>

  <div style="font-size:0.82rem;color:#6B7280;line-height:1.55;
              margin-bottom:1rem;">{desc}</div>

  <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.05em;color:#6B7280;margin-bottom:0.4rem;">
    Scoring breakdown
  </div>
  <table style="width:100%;border-collapse:collapse;">
    <thead>
      <tr style="border-bottom:1px solid #E2E5EA;">
        <th style="text-align:left;padding:4px 8px;font-size:0.78rem;
                   color:#6B7280;font-weight:600;">Dimension</th>
        <th style="text-align:center;padding:4px 8px;font-size:0.78rem;
                   color:#6B7280;font-weight:600;">Score</th>
        <th style="text-align:left;padding:4px 8px;font-size:0.78rem;
                   color:#6B7280;font-weight:600;">Signal</th>
      </tr>
    </thead>
    <tbody>{sub_rows}</tbody>
  </table>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Filters")

    count_slot = st.empty()   # filled after filtering

    st.divider()
    fetch_btn = st.button("Refresh from market", type="primary",
                          use_container_width=True,
                          help="Query Yahoo screener + fetch fresh fundamentals")

    with st.expander("Geography & Sector", expanded=True):
        region_options    = {v: k for k, v in REGION_LABELS.items()}
        selected_countries = st.multiselect(
            "Countries / Regions",
            options=sorted(REGION_LABELS.values()),
            default=[],
            placeholder="All countries",
        )
        selected_region_codes = [region_options[c] for c in selected_countries
                                 if c in region_options]
        selected_sectors = st.multiselect(
            "Sectors", options=ALL_SECTORS, default=["Technology"],
            help="Used when fetching from Yahoo Finance screener.",
        )

    with st.expander("Scale", expanded=True):
        mc_min, mc_max = st.slider("Market Cap ($B)", 0.1, 500.0,
                                   (1.0, 60.0), step=0.5)

    with st.expander("Financials", expanded=False):
        rg_min,  rg_max  = st.slider("Revenue Growth (%)",  -20, 100, (-20, 100), step=1)
        em_min,  em_max  = st.slider("EBITDA Margin (%)",   -50,  80, (-50,  80), step=1)
        fcf_min, fcf_max = st.slider("FCF Margin (%)",      -30,  60, (-30,  60), step=1)
        evr_max  = st.slider("Max EV / Revenue", 1.0, 50.0, 50.0, step=0.5)
        nd_max   = st.number_input("Max Net Debt / EBITDA", value=None,
                                    min_value=0.0, max_value=20.0, step=0.5,
                                    placeholder="No limit")
        cache_now      = universe_agent.load_cache()
        all_industries = sorted({p.get("industry", "")
                                  for p in cache_now.values() if p.get("industry")})
        selected_industries = st.multiselect(
            "Industry", options=all_industries, default=[],
            placeholder="All industries",
        )

    with st.expander("Sort & Display", expanded=False):
        sort_by  = st.selectbox("Sort by",
                                ["PE Score", "Market Cap ($B)", "Rev Growth (%)",
                                 "EBITDA Margin (%)", "FCF Margin (%)",
                                 "EV / Revenue", "Net Debt / EBITDA"])
        sort_asc = st.checkbox("Sort ascending", value=False)

    st.divider()
    st.caption(f"Cache: {len(cache_now)} companies  ·  filters apply instantly")


# ── main ──────────────────────────────────────────────────────────────────────
st.title("PE Sourcing Copilot")
st.caption("Software company screener for PE buyout sourcing — powered by Yahoo Finance")

tab1, tab2 = st.tabs(["Screener", "Sourcing Memos"])

with tab1:

    # Live fetch ───────────────────────────────────────────────────────────────
    if fetch_btn:
        filters = {
            "min_market_cap": mc_min * 1e9,
            "max_market_cap": mc_max * 1e9,
            "regions":  selected_region_codes or ["us"],
            "sectors":  selected_sectors or ["Technology"],
        }
        progress_bar = st.progress(0, text="Querying Yahoo Finance screener…")
        status_text  = st.empty()

        def on_progress(done, total, ticker):
            if total == 0: return
            label = (f"Fetching {ticker} … ({done}/{total})"
                     if ticker != "done" else "Done!")
            progress_bar.progress(done / total, text=label)
            status_text.caption(label)

        profiles_live = universe_agent.run_live(filters, progress_cb=on_progress)
        progress_bar.empty()
        status_text.empty()
        st.session_state["profiles"]    = profiles_live
        st.session_state["profiles_df"] = profiles_to_df(profiles_live)
        st.success(f"Fetched {len(profiles_live)} software companies from Yahoo Finance.")

    # Load from cache on first visit ──────────────────────────────────────────
    if "profiles_df" not in st.session_state:
        raw_profiles = universe_agent.run_from_cache(
            {"min_market_cap": 0, "max_market_cap": 1e18})
        if raw_profiles:
            st.session_state["profiles"]    = raw_profiles
            st.session_state["profiles_df"] = profiles_to_df(raw_profiles)

    # Render ──────────────────────────────────────────────────────────────────
    if "profiles_df" in st.session_state:
        df_all   = st.session_state["profiles_df"]
        profiles = st.session_state.get("profiles", {})

        df = df_all[
            df_all["_market_cap"].notna() &
            (df_all["_market_cap"] >= mc_min * 1e9) &
            (df_all["_market_cap"] <= mc_max * 1e9)
        ].copy()

        country_filter = (selected_countries
                          if (selected_countries and "_country" in df.columns)
                          else [])
        df = apply_filters(df, rg_min, rg_max, em_min, em_max,
                           fcf_min, fcf_max, evr_max, nd_max,
                           country_filter, selected_industries)

        # Update sidebar chip now that we know the count
        with count_slot:
            filter_count(len(df), len(df_all))

        if df.empty:
            st.info("No companies match the current filters.")
        else:
            # Zone 1 — Summary metric strip ───────────────────────────────
            section("Overview")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Companies", f"{len(df):,}")
            med_score = df["PE Score"].median()
            med_rg    = df["Rev Growth (%)"].median()
            med_em    = df["EBITDA Margin (%)"].median()
            med_evr   = df["EV / Revenue"].median()
            m2.metric("Median PE Score",     f"{med_score:.2f}" if pd.notna(med_score) else "—")
            m3.metric("Median Rev Growth",   f"{med_rg:.1f}%"   if pd.notna(med_rg)    else "—")
            m4.metric("Median EBITDA Margin",f"{med_em:.1f}%"   if pd.notna(med_em)    else "—")
            m5.metric("Median EV / Revenue", f"{med_evr:.1f}x"  if pd.notna(med_evr)   else "—")

            # Zone 2 — Charts ─────────────────────────────────────────────
            section("Distribution")
            render_charts(df)

            # Zone 3 — Ranked table ───────────────────────────────────────
            section("Ranked Companies")
            st.caption(f"{len(df)} companies · sorted by {sort_by}")
            render_table(df, sort_by, sort_asc)

            # Zone 4 — Company deal card ───────────────────────────────────
            section("Company Deep-Dive")
            sorted_tickers = (df.sort_values("PE Score", ascending=False)
                              ["Ticker"].tolist())
            cache = universe_agent.load_cache()

            def _fmt_option(t):
                name  = cache[t]["company_name"] if t in cache else t
                score = df.loc[df["Ticker"] == t, "PE Score"]
                sc_str = f"  [{score.iloc[0]:.2f}]" if len(score) else ""
                return f"{t} — {name}{sc_str}"

            selected_ticker = st.selectbox(
                "Select a company to view full detail",
                options=sorted_tickers,
                format_func=_fmt_option,
            )
            if selected_ticker and profiles:
                render_deal_card(selected_ticker, df, profiles)
            elif selected_ticker:
                st.info("Click **Refresh from market** to load full profiles.")

    else:
        st.info("No cached data yet. Click **Refresh from market** in the sidebar.")


# ── Tab 2: Sourcing Memos ─────────────────────────────────────────────────────
with tab2:
    outputs = os.path.join(os.path.dirname(__file__), "outputs")
    memos = {}
    if os.path.isdir(outputs):
        for fname in os.listdir(outputs):
            if fname.startswith("memo_") and fname.endswith(".md"):
                ticker = fname[5:-3]
                with open(os.path.join(outputs, fname)) as fh:
                    memos[ticker] = fh.read()

    if not memos:
        st.info("No memos yet. Run `python main.py` locally to generate sourcing memos.")
    else:
        cache = universe_agent.load_cache()
        ticker_choice = st.selectbox(
            "Select company",
            options=sorted(memos.keys()),
            format_func=lambda t: (f"{t} — {cache[t]['company_name']}"
                                   if t in cache else t),
        )
        st.markdown(memos[ticker_choice])
        st.download_button("Download memo", memos[ticker_choice],
                           f"memo_{ticker_choice}.md", "text/markdown")
