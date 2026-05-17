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
# SCORING THESIS (v2 — "buyout fit", not "company quality")
# ----------------------------------------------------------
# v1 of this model scored companies on raw financial quality (high margin,
# high growth, cheap). Evaluation showed that does NOT predict take-privates:
# PE firms acquire mid-cap, moderate-growth businesses with an OPERATIONAL
# IMPROVEMENT GAP — not already-perfect compounders, which are too expensive
# and too optimised to buy. v2 scores buyout FIT:
#   - scale_fit            : is it in the mid-cap LBO sweet spot
#   - valuation_attractiveness : is it cheap enough to underwrite
#   - cash_flow_stability  : can it service LBO debt (still matters)
#   - improvement_headroom : moderate margins = room to expand post-deal
#   - growth_moderation    : moderate (not hyper-) growth scores highest
#   - leverage_capacity    : low existing debt = room to add leverage
# ---------------------------------------------------------------------------
SCORE_WEIGHTS = {
    "scale_fit":                0.22,  # mid-cap sweet spot — strongest signal
    "valuation_attractiveness": 0.22,  # must be underwritable, not richly priced
    "cash_flow_stability":      0.18,  # FCF to service debt
    "improvement_headroom":     0.16,  # margin expansion opportunity
    "growth_moderation":        0.12,  # steady > explosive for an LBO
    "leverage_capacity":        0.10,  # room to add debt
}

# ---------------------------------------------------------------------------
# Threshold tables: map a raw metric to a 1-5 subscore.
# Format: list of (bound, score). For higher-is-better, read high-to-low;
# for lower-is-better, read as ascending bounds (see scoring_agent.py).
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # FCF margin — positive, stable cash generation (higher better, but
    # extreme values are not required — a positive FCF margin already scores well)
    "cash_flow_stability": [(0.20, 5), (0.12, 4), (0.05, 3), (0.0, 2), (-1e9, 1)],
    # Net debt / EBITDA — LOWER is better (lower existing leverage = more room)
    "leverage_capacity":   [(1.5, 5), (3.0, 4), (4.5, 3), (6.5, 2), (1e9, 1)],
    # EV / Revenue — LOWER is better (cheap enough to underwrite an LBO)
    "valuation_attractiveness": [(4.0, 5), (7.0, 4), (10.0, 3), (14.0, 2), (1e9, 1)],
    # improvement_headroom and growth_moderation use "band" scoring —
    # a middle range scores highest — handled by functions in scoring_agent.py
    # scale_fit also handled by a dedicated function.
}

# improvement_headroom: EBITDA margin BANDS. Moderate margins score highest
# (room to improve); already-elite OR very weak margins score lower.
IMPROVEMENT_BANDS = [
    (0.15, 0.30, 5),   # sweet spot: solid but improvable
    (0.30, 0.45, 4),   # good, less headroom
    (0.08, 0.15, 4),   # thin but fixable
    (0.45, 1.00, 3),   # already elite — little headroom
    (0.00, 0.08, 2),   # very weak — execution risk
    (-1e9, 0.00, 1),   # loss-making
]

# growth_moderation: revenue-growth BANDS. Moderate growth scores highest;
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
