# Agentic AI Private Equity Sourcing Copilot

An evaluated multi-agent framework that automates the first-pass deal-sourcing
workflow of a private equity analyst: it defines a target universe, retrieves
company financials, scores each company on **buyout fit**, generates short
investment-screening memos, and produces a ranked shortlist — then **evaluates**
its ranking against verified PE take-private outcomes.

Built as the capstone for *Advanced Machine Learning in Finance*.

---

## What it does

```
User filters
   -> Universe Agent        define candidate universe (curated, labelled)
   -> Data Retrieval Agent  fetch financial profiles (yfinance, cached)
   -> PE Scoring Agent       deterministic buyout-fit scoring (6 subscores)
   -> Coordinator            rank + select top-K
   -> Memo Generation Agent  LLM-written sourcing memos for the top-K
   -> Ranked PE target shortlist + memos
```

The **scoring is deterministic and rule-based** (auditable, reproducible); the
**LLM is used only to write memos**, never to score. This separation is what
makes the evaluation defensible.

---

## Setup (run this in Claude Code on your own machine)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get one API key
You need a single key — the Anthropic API key, used only by the Memo Agent.
- Go to **console.anthropic.com** -> Billing -> add a little credit (~$5 is plenty).
- API Keys -> Create Key -> copy it (starts with `sk-ant-`).

`yfinance` needs **no key**.

### 3. Provide the key (pick one)
```bash
# Option A — environment variable for this terminal session
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```
```bash
# Option B — a .env file in this folder (auto-loaded; .gitignore protects it)
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' > .env
```

---

## Run

```bash
python main.py            # full pipeline: data -> score -> memos -> shortlist
python eval/evaluate.py   # evaluation: agentic ranking vs baseline
```

Outputs land in `outputs/`:
- `ranked_shortlist.csv` — every company, PE score, 6 subscores, ground-truth label
- `memo_<TICKER>.md` — one sourcing memo per top-K company

Without an API key the pipeline still runs end-to-end and emits clearly-labelled
**template** memos; set the key for real LLM memos.

---

## IMPORTANT — data fixture vs live data

`data/cache.json` ships as a **development fixture** (`data/make_dev_fixture.py`):
realistic approximate financials so the pipeline can be demonstrated offline.

**For your real submission, use live data:**
```bash
rm data/cache.json
python main.py            # Data Retrieval Agent repopulates cache from live yfinance
```
The Data Retrieval Agent fetches from Yahoo Finance and caches the result, so
subsequent runs (including evaluation) are fast and reproducible.

---

## Project structure

```
pe_sourcing_copilot/
  config.py              all tunable parameters: filters, weights, thresholds
  main.py                Coordinator Agent + entry point
  agents/
    universe_agent.py    Step 1 — define candidate universe
    data_agent.py        Step 2 — retrieve + cache financial profiles
    scoring_agent.py     Step 3 — deterministic buyout-fit scoring
    memo_agent.py        Step 4 — LLM-generated sourcing memos
    baseline.py          naive market-cap ranker (for evaluation only)
  eval/
    metrics.py           Precision@K, Recall@K, NDCG@K
    evaluate.py          evaluation runner: agentic vs baseline
  data/
    universe.csv         curated 40-company universe + verified PE labels
    make_dev_fixture.py  generates the offline development fixture
  outputs/               generated shortlist + memos
  REPORT.md              capstone report scaffold
```

---

## Evaluation summary

The system is evaluated as a ranking problem: how well does the PE score rank
verified PE take-private targets above companies that stayed public? It is
compared against a naive market-cap baseline using Precision@K, Recall@K and
NDCG@K. See `REPORT.md` for methodology, results, limitations, and future work.

**This is a methodology demonstration on a small proxy dataset, not a validated
predictor.** Limitations are stated explicitly in the report.
