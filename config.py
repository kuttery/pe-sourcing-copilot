"""
config.py — Central configuration for the PE Sourcing Copilot.

All tunable parameters live here so the scoring logic stays transparent
and reproducible. Nothing in the scoring agent is hidden or hard-coded.
"""

# ---------------------------------------------------------------------------
# Default user filters (the Universe Agent applies these to data/universe.csv)
# ---------------------------------------------------------------------------
DEFAULT_FILTERS = {
    "sector": "Software",      # None = no sector filter
    "geography": None,         # None = no geography filter
    "min_market_cap": 1e9,     # USD; None to disable
    "max_market_cap": 60e9,    # USD; None to disable
}

# ---------------------------------------------------------------------------
# PE scoring: subscore weights (must sum to 1.0)
#
# SCORING THESIS (v3 — "buyout fit", not "company quality")
# ----------------------------------------------------------
# v1 scored raw quality (high margin, high growth, cheap) — did not predict
# take-privates.  v2 scored buyout FIT (mid-cap, moderate growth, room to
# improve).  v3 keeps the v2 thesis and enriches three dimensions with
# income-statement data (gross_profit, ebit) collected from 10-Ks:
#
#   scale_fit         (0.22) — mid-cap LBO sweet spot, unchanged
#   valuation         (0.20) — EV/Revenue, same thresholds (was 0.22)
#   cash_generation   (0.18) — FCF margin + FCF/EBITDA conversion
#   margin_headroom   (0.16) — EBITDA margin band (0.6) + gross margin (0.4)
#   growth_quality    (0.12) — banded revenue growth; Rule-of-40 in rationale
#   leverage_capacity (0.12) — net debt/EBITDA only (was 0.10)
#
# Design decisions:
#   • interest_coverage dropped from leverage: EBIT/interest_expense
#     anti-correlates with PE targets (pre-profitability LBO candidates have
#     negative EBIT by construction).
#   • Rule-of-40 not averaged into growth_quality: doing so softened the
#     hyper-growth penalty that correctly down-ranks richly-priced growers.
#   • EBITDA bands kept as primary margin signal (0.6 weight): directly tests
#     the improvement thesis; gross margin added as quality check (0.4 weight).
# ---------------------------------------------------------------------------
SCORE_WEIGHTS = {
    "scale_fit":         0.22,
    "valuation":         0.20,
    "cash_generation":   0.18,
    "margin_headroom":   0.16,
    "growth_quality":    0.12,
    "leverage_capacity": 0.12,
}

# ---------------------------------------------------------------------------
# Threshold tables: map a raw metric to a 1-5 subscore.
# Format: list of (bound, score). For higher-is-better, read high-to-low;
# for lower-is-better, read as ascending bounds (see scoring_agent.py).
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # EV/Revenue — lower is better (same cut-points as v2)
    "valuation": [(4.0, 5), (7.0, 4), (10.0, 3), (14.0, 2), (1e9, 1)],

    # FCF margin — higher is better
    "fcf_margin": [(0.20, 5), (0.12, 4), (0.05, 3), (0.0, 2), (-1e9, 1)],

    # FCF conversion = FCF / EBITDA — higher is better
    # (only used when EBITDA > 0; falls back to FCF margin score otherwise)
    "fcf_conversion": [(0.75, 5), (0.50, 4), (0.25, 3), (0.0, 2), (-1e9, 1)],

    # Gross margin — higher is better (software quality signal)
    # Floor at 0.45 avoids penalising hybrid SaaS/services gross margins
    "gross_margin": [(0.70, 5), (0.60, 4), (0.45, 3), (0.35, 2), (-1e9, 1)],

    # Net debt / EBITDA — lower is better (room to add LBO leverage)
    "net_debt_ebitda": [(1.5, 5), (3.0, 4), (4.5, 3), (6.5, 2), (1e9, 1)],
}

# EBITDA margin BANDS (primary signal in margin_headroom).
# Moderate margins score highest — they signal room to improve post-deal.
IMPROVEMENT_BANDS = [
    (0.15, 0.30, 5),   # sweet spot: solid but improvable
    (0.30, 0.45, 4),   # good, less headroom
    (0.08, 0.15, 4),   # thin but fixable
    (0.45, 1.00, 3),   # already elite — little headroom
    (0.00, 0.08, 2),   # very weak — execution risk
    (-1e9, 0.00, 1),   # loss-making
]

# Revenue growth BANDS. Moderate growth scores highest;
# hyper-growth (expensive, hard to lever) and decline both score lower.
GROWTH_BANDS = [
    (0.08, 0.20, 5),   # steady, durable growth — ideal LBO profile
    (0.20, 0.30, 4),   # fast but still workable
    (0.03, 0.08, 4),   # slow but stable
    (0.30, 2.00, 3),   # hyper-growth — usually too richly valued
    (0.00, 0.03, 3),   # flat
    (-1e9, 0.00, 2),   # declining
]

# Mid-cap LBO sweet spot for scale_fit (USD)
SCALE_SWEET_SPOT = (2e9, 15e9)

# Number of companies to carry into memo generation / shortlist
TOP_K = 5

# Anthropic model for the Memo Agent
MEMO_MODEL = "claude-haiku-4-5-20251001"

# Evaluation: K values for Precision@K / Recall@K / NDCG@K
EVAL_K_VALUES = [3, 5, 10]

# ---------------------------------------------------------------------------
# V2 config — archived for ablation / reference only
# ---------------------------------------------------------------------------
_V2_SCORE_WEIGHTS = {
    "scale_fit":                0.22,
    "valuation_attractiveness": 0.22,
    "cash_flow_stability":      0.18,
    "improvement_headroom":     0.16,
    "growth_moderation":        0.12,
    "leverage_capacity":        0.10,
}
_V2_THRESHOLDS = {
    "cash_flow_stability":       [(0.20, 5), (0.12, 4), (0.05, 3), (0.0, 2), (-1e9, 1)],
    "leverage_capacity":         [(1.5, 5), (3.0, 4), (4.5, 3), (6.5, 2), (1e9, 1)],
    "valuation_attractiveness":  [(4.0, 5), (7.0, 4), (10.0, 3), (14.0, 2), (1e9, 1)],
}
