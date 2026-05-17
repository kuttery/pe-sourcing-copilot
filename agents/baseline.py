"""
agents/baseline.py

Baseline ranker — used ONLY by the evaluation framework.

To show the agentic PE-scoring pipeline adds value, we compare it against
a naive baseline a junior analyst might use without any scoring model:
rank the universe purely by company size (market capitalisation).

This is a fair, non-strawman baseline: size is a real and common first-pass
screen, and it requires the same input data as the full pipeline. If the
agentic ranking does not beat it on Precision@K / NDCG, that is an honest
and reportable result.
"""


def rank(profiles: dict) -> list:
    """Return tickers ranked by market cap descending (largest first).

    Companies with missing market cap are pushed to the bottom.
    """
    def cap(p):
        v = p.get("market_cap")
        return v if v is not None else -1.0

    ordered = sorted(profiles.values(), key=cap, reverse=True)
    return [p["ticker"] for p in ordered]


if __name__ == "__main__":
    demo = {
        "A": {"ticker": "A", "market_cap": 5e9},
        "B": {"ticker": "B", "market_cap": 20e9},
        "C": {"ticker": "C", "market_cap": None},
    }
    print(rank(demo))  # expect ['B', 'A', 'C']
