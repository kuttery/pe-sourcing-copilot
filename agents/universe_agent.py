"""
agents/universe_agent.py

Universe Agent — Step 1 of the pipeline.

Defines the candidate company universe by applying user filters (sector,
geography, market-cap range) to the curated, labelled universe in
data/universe.csv. The universe is fixed and verified so that downstream
evaluation is reproducible.

Note: market-cap filtering needs live data, so it is applied AFTER the
Data Retrieval Agent runs. This agent applies the static filters only
(sector, geography) and returns candidate tickers.
"""
import os
import pandas as pd

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")


def run(filters: dict) -> pd.DataFrame:
    """Return the filtered candidate universe as a DataFrame.

    Args:
        filters: dict that may contain 'sector' and 'geography' keys.
                 Market-cap filters are applied later (need live data).

    Returns:
        DataFrame of candidate companies with their ground-truth labels.
    """
    df = pd.read_csv(UNIVERSE_PATH)
    n_start = len(df)

    sector = filters.get("sector")
    if sector:
        df = df[df["sector"].str.lower() == sector.lower()]

    geography = filters.get("geography")
    if geography:
        df = df[df["geography"].str.lower() == geography.lower()]

    df = df.reset_index(drop=True)
    print(f"[UniverseAgent] {n_start} companies -> {len(df)} after static filters "
          f"(sector={sector}, geography={geography})")
    return df


if __name__ == "__main__":
    from config import DEFAULT_FILTERS
    out = run(DEFAULT_FILTERS)
    print(out[["ticker", "company_name", "pe_acquired"]].to_string(index=False))
