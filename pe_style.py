"""
pe_style.py — reusable styled components for the PE sourcing app.

Import what you need:
    from pe_style import load_css, score_badge, deal_card_open, deal_card_close,
                         filter_count, section, CHART_COLORS
"""

from typing import Optional
import streamlit as st


def load_css(path: str = "styles.css") -> None:
    """Inject the stylesheet once. Call right after st.set_page_config()."""
    try:
        with open(path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Stylesheet not found at {path} — app will use defaults.")


def score_color(score: float) -> str:
    """Hex color for a 1–5 PE score. ≥4.5 green, ≥3.5 navy, <3.5 orange."""
    if score >= 4.5:
        return "#1F7A4D"
    if score >= 3.5:
        return "#1B2A4A"
    return "#C2410C"


def score_badge(score: float, is_top: bool = False) -> str:
    """Return an HTML <span> for a colored score badge (1–5 scale).

    Use inside st.markdown(..., unsafe_allow_html=True).
    """
    if is_top:
        cls = "pe-score pe-score-top"
    elif score >= 4.5:
        cls = "pe-score pe-score-high"
    elif score >= 3.5:
        cls = "pe-score pe-score-mid"
    else:
        cls = "pe-score pe-score-low"
    return f'<span class="{cls}">{score:.2f}</span>'


def section(label: str) -> None:
    """Render a themed section divider with an uppercase label."""
    st.markdown('<hr class="pe-section">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="pe-section-label">{label}</div>',
        unsafe_allow_html=True,
    )


def filter_count(n: int, total: Optional[int] = None) -> None:
    """Render the live match-count chip at the top of the sidebar."""
    text = f"{n:,} companies match"
    if total is not None:
        text += f"  ·  {total:,} cached"
    st.markdown(
        f'<div class="pe-filter-count">{text}</div>',
        unsafe_allow_html=True,
    )


def deal_card_open(name: str, subtitle: str = "") -> None:
    """Open a deal card div. Pair every call with deal_card_close()."""
    st.markdown(
        f'<div class="pe-card">'
        f'<div class="pe-card-title">{name}</div>'
        f'<div class="pe-card-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )


def deal_card_close() -> None:
    """Close a deal card opened with deal_card_open()."""
    st.markdown("</div>", unsafe_allow_html=True)


# ── On-theme chart palette ────────────────────────────────────────────────────
CHART_COLORS = {
    "primary":   "#1B2A4A",   # navy — main bars / series
    "secondary": "#B8954A",   # gold — secondary series
    "positive":  "#1F7A4D",
    "caution":   "#C2410C",
    "grid":      "#E2E5EA",
    "axis_text": "#6B7280",
    "bg":        "#FFFFFF",
}
