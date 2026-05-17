# An Evaluated Agentic AI Framework for Private Equity Deal Sourcing

*Capstone — Advanced Machine Learning in Finance*

---

## 1. Abstract

Private equity deal sourcing is a labour-intensive, analyst-driven process: a team must screen hundreds of companies against acquisition criteria before a shortlist reaches an investment committee. This paper presents an evaluated agentic AI framework that automates that first-pass screen for the software sector. The system is a sequential multi-agent pipeline in which a Universe Agent defines a candidate set, a Data Retrieval Agent fetches and caches financial profiles, a PE Scoring Agent assigns deterministic buyout-fit scores, and a Memo Generation Agent produces LLM-written sourcing memos for the top-ranked candidates. The central design choice is a strict separation of judgement: scoring uses a transparent, rule-based function with auditable thresholds; Claude (claude-haiku-4-5-20251001) is invoked only to synthesise narrative prose from those scores, never to determine them. Against a ground truth of eleven verified PE take-private transactions within a 36-company universe, the pipeline achieves Precision@10 = 0.200 and NDCG@10 = 0.164, placing two actual PE-acquired companies in the top ten. A naive market-cap ranker scores 0.000 on every metric, confirming that the buyout-fit framing captures a signal orthogonal to raw company scale.

## 2. Problem Statement and Financial Relevance

First-pass deal sourcing — colloquially "top-of-funnel" screening — is among the most repetitive tasks in a PE analyst's workflow. The analyst must apply a consistent set of financial and qualitative criteria to a large universe of potential targets and compress it to a short, defensible list before deeper diligence begins. The criteria are well understood in the industry (scale, valuation, cash generation, leverage headroom), but applying them systematically across scores of companies is time-consuming and subject to individual bias.

The key conceptual contribution of this framework is the distinction between *company quality* and *buyout fit*. A PE take-private is not driven by the same criteria as a long-only equity purchase. A hyper-growth SaaS compounder with 40 % revenue growth and a 25x EV/Revenue multiple may be an outstanding equity investment, but it is a poor LBO candidate: the valuation is too rich to underwrite, the leverage capacity is limited, and there is little operational improvement gap to exploit post-acquisition. Conversely, a mid-cap software company with moderate growth (10–15 %), a measurable EBITDA margin gap versus peers, and low existing leverage is structurally attractive: the sponsor can add debt, run a margin improvement playbook, and exit at a higher multiple. This "buyout fit" framing — operationalised as six subscores described in Section 5 — is what the PE Scoring Agent implements.

Framing the problem as an *information-retrieval ranking task* enables rigorous evaluation. Each company is either a relevant document (PE-acquired = 1) or not (0); the pipeline produces a ranked list; Precision@K, Recall@K, and NDCG@K measure how well the relevant documents surface at the top of that list. A market-cap ranker serves as the baseline — a non-trivial first-pass screen that is fair and uses the same underlying data.

## 3. System Architecture

A sequential multi-agent pipeline with a coordinator:

```
User filters
   -> Universe Agent        define candidate universe
   -> Data Retrieval Agent  fetch + cache financial profiles
   -> PE Scoring Agent      deterministic buyout-fit scoring
   -> Coordinator           rank + select top-K
   -> Memo Generation Agent LLM-written sourcing memos
   -> Ranked shortlist + memos
```

**Design principle — separation of judgement.** Scoring is *deterministic and
rule-based* so every number is auditable and the evaluation is reproducible.
The LLM is used *only* in the Memo Agent to synthesise narrative memos — never
to score. This is a deliberate choice for academic defensibility.

### 3.1 Agent definitions

**Universe Agent** (`agents/universe_agent.py`). Takes a filters dictionary (sector, geography, market-cap bounds) as input and returns a DataFrame of candidate companies from the curated `data/universe.csv`. Static filters (sector, geography) are applied immediately; market-cap bounds require live data and are applied downstream. The agent exists to isolate the "what is the universe?" decision from data retrieval, making it easy to swap in a different ticker list or add new filter dimensions without touching any downstream agent.

**Data Retrieval Agent** (`agents/data_agent.py`). Takes the universe DataFrame and returns a dictionary of financial profiles keyed by ticker. For each company it calls `yfinance` to obtain market cap, revenue, EBITDA, free cash flow, total debt, cash, revenue growth, and enterprise value, then derives ratios (EBITDA margin, FCF margin, EV/Revenue, net debt/EBITDA). Profiles are written to `data/cache.json` so that repeated pipeline runs — including all evaluation runs — are fast, reproducible, and resilient to API rate limits. Missing fields are returned as `None` rather than imputed, so scoring can handle gaps explicitly.

**PE Scoring Agent** (`agents/scoring_agent.py`). Takes the profiles dictionary and returns a scored dictionary with six integer subscores (1–5) and a weighted final score per company. All thresholds and weights are read from `config.py`. Missing subscores default to a neutral 3 so that a single data gap does not unfairly sink a company, but the gap is flagged. The agent is entirely deterministic: identical inputs always produce identical scores. No LLM is called.

**Coordinator** (`main.py`). Orchestrates the sequential pipeline, applies the market-cap filter after data retrieval, calls `scoring_agent.run()`, ranks companies by `pe_score` descending, writes `outputs/ranked_shortlist.csv`, selects the top-K tickers, and hands them to the Memo Agent. It is deliberately thin — its only logic is ordering and filtering.

**Memo Generation Agent** (`agents/memo_agent.py`). Takes the top-K profiles and their scores and calls the Anthropic Claude API (model: `claude-haiku-4-5-20251001`) to produce a structured sourcing memo for each company. The prompt provides the company description, key financials, deterministic subscores, and rationale strings. The LLM is instructed to synthesise narrative commentary tied to the provided numbers, not to invent data. If no API key is present, the agent emits a clearly labelled template memo so the rest of the pipeline — including evaluation — runs without interruption.

## 4. Data Pipeline

**Source.** All financial data is obtained from Yahoo Finance via the `yfinance` Python library — no API key required, a single dependency, and sufficient coverage for the 36-company US-listed Software universe. This scope choice is intentional for a capstone prototype: the alternative providers (SEC EDGAR, FMP, Alpha Vantage, Finnhub) either require paid plans for full coverage, have rate limits that complicate reproducible evaluation, or have recently migrated endpoint paths (FMP deprecated all `/v3/` endpoints in favour of `/stable/` paths in 2025). The `yfinance` approach delivers the six metrics the scoring model requires for all currently-listed companies without additional infrastructure.

**Profile structure.** For each company the agent records: market cap, total revenue, EBITDA, EBITDA margin, free cash flow, FCF margin, revenue growth (year-over-year), total debt, cash, net debt, net debt/EBITDA, enterprise value, and EV/Revenue, plus a business description and industry tag. Derived ratios are computed only when all required inputs are present; otherwise they are left as `None`.

**Caching.** Profiles are serialised to `data/cache.json` on first fetch and loaded from cache on all subsequent runs. The cache is the unit of reproducibility: evaluation results are stable so long as the cache is not deleted. The cache also enables the hybrid approach described below.

**Hybrid cache for delisted positives.** All eleven PE-acquired companies in the ground truth have been taken private and are no longer listed; `yfinance` returns empty profiles for them. To make the evaluation meaningful, their last publicly available financial data — from the final annual report (10-K) filed before the respective acquisition announcement — was extracted and manually inserted into the cache using the same field schema. This means positives are scored on *pre-acquisition* financials and negatives on *current* (2024–2025) yfinance data; the implications are discussed in Section 8.

**Market-cap filter.** After retrieval, companies outside the [$1B, $60B] market-cap band defined in `config.py` are excluded from the scored shortlist. This narrows the evaluated set from 40 to 28 companies (note: `evaluate.py` works against the full 36-company universe including companies below the filter threshold, which is why PRO appears in evaluation but not in the ranked output).

## 5. Scoring Methodology

PE attractiveness = weighted sum of six subscores, each an integer 1–5,
producing a final 1–5 score. All weights and thresholds live in `config.py`.

| Subscore | Metric | Rationale |
|---|---|---|
| Scale fit | Market cap vs mid-cap sweet spot | LBO targets cluster in the mid-cap range |
| Valuation attractiveness | EV / Revenue (lower better) | Must be cheap enough to underwrite |
| Cash flow stability | FCF margin | Positive cash to service LBO debt |
| Improvement headroom | EBITDA margin *band* | Moderate margins = room to expand post-deal |
| Growth moderation | Revenue growth *band* | Steady growth beats hyper-growth for an LBO |
| Leverage capacity | Net debt / EBITDA (lower better) | Room to add acquisition leverage |

Two subscores — improvement headroom and growth moderation — use *band scoring* rather than monotone thresholds, and this is the core modelling insight. For improvement headroom, EBITDA margins in the 15–30 % range score a 5: the company is generating real cash but has not yet reached the efficiency ceiling its cost structure permits, which means a sponsor can extract margin expansion through go-to-market rationalisation, platform consolidation, or procurement discipline. Margins already above 45 % score a 3: the company is well-run and the obvious levers have been pulled — future sponsors pay a premium for quality with little room left to improve it. Similarly, growth moderation scores highest for 8–20 % revenue growth: fast enough to support a compelling equity story but slow enough that the valuation has not detached from the underlying cash flow. A company growing at 35 %+ annually almost always trades at a multiple incompatible with LBO financing; a declining company introduces cash flow risk that makes debt service harder to model. The band approach captures both tails of the distribution as unattractive for different reasons, which a simple "higher is better" scoring rule would miss entirely.

### 5.1 Scoring thesis revision (ablation)
This is a genuine finding worth reporting. **Version 1** scored raw company
quality (maximise margin, growth; minimise valuation). It **failed**: it ranked
healthy large-cap SaaS companies top and scored Precision@5 = 0.00 against the
PE-acquired ground truth. **Version 2** reframed the target as *buyout fit*
(scale, underwritable valuation, improvement headroom, moderate growth) and
separated cleanly from the baseline. Reporting both is an honest ablation.

## 6. Evaluation Framework

Deal sourcing is framed as a **ranking / information-retrieval** problem.

**Ground truth.** The `pe_acquired` label in `data/universe.csv` marks companies verified — via public reporting — to have been taken private by PE/buyout firms (e.g. Smartsheet/Vista+Blackstone, Squarespace/Permira, Instructure/KKR, PowerSchool/Bain, Dayforce & Olo/Thoma Bravo, Jamf/Francisco Partners). This is a **proxy** for "attractive target" with an important asymmetry: a company that has *not* been acquired is not necessarily unattractive — it may simply not yet have attracted a bid, or its controlling shareholders may have declined approaches. The ground truth therefore contains false negatives among the unlabelled companies, which understates the pipeline's true precision. The base rate (11/36 = 30.6 %) is also inflated by construction: the universe was seeded with known positives, which would not be the case in a production deployment where the positives are the unknowns to be discovered.

One company in the universe — Catalent — was acquired by Novo Holdings, a strategic investment vehicle of Novo Nordisk, rather than a classic LBO sponsor pursuing financial engineering. Its inclusion as a positive is a borderline case: the deal was driven by strategic supply-chain rationale, not the typical buyout value-creation playbook. Results are reported with Catalent included in the ground truth as labelled; excluding it would modestly improve the PE-specific precision of the pipeline.

**Metrics.** Precision@K, Recall@K, NDCG@K at K = 3, 5, 10.

**Baseline.** A naive market-cap ranker — a fair, non-strawman first-pass screen
that uses the same data as the full pipeline.

### 6.1 Results

| Metric | K | Agentic | Baseline | Delta |
|---|---|---|---|---|
| Precision | 3 | 0.000 | 0.000 | +0.000 |
| Precision | 5 | 0.200 | 0.000 | +0.200 |
| Precision | 10 | 0.200 | 0.000 | +0.200 |
| Recall | 5 | 0.091 | 0.000 | +0.091 |
| Recall | 10 | 0.182 | 0.000 | +0.182 |
| NDCG | 5 | 0.131 | 0.000 | +0.131 |
| NDCG | 10 | 0.164 | 0.000 | +0.164 |

The results should be read in two parts. First, the pipeline consistently beats the market-cap baseline on every metric at K ≥ 5, with the baseline scoring 0.000 across the board. This is not surprising given the nature of the task: the largest companies by market cap — CrowdStrike, Salesforce, ServiceNow, Palo Alto Networks — are precisely the companies that do *not* get taken private, because their scale and valuation make LBO financing structurally infeasible. A market-cap ranker is therefore an anti-signal for buyout targets; the pipeline's non-zero scores confirm that the buyout-fit criteria are capturing something real.

Second, the absolute numbers are modest: two of ten shortlisted companies (INST at rank 5, DAY at rank 6) are verified PE acquisitions, and neither surfaces in the top three. The limitations are structural rather than model-specific. The 36-company universe is small; with only 11 labelled positives there is limited resolution to separate a good ranking from a lucky one. The hybrid cache means positives are evaluated on older financial data while negatives use current data, which introduces a temporal confound. And the three companies ranked 1–4 (PCTY, DOCU, ALRM, OKTA) are genuinely plausible PE targets by the framework's criteria — their absence from the ground truth may reflect timing (no announced deal as of the labelling date) rather than true unattractiveness. The framework is best understood as a *methodology demonstration* of the buyout-fit scoring approach, with the evaluation confirming directional validity against a fair baseline.

## 7. Sample Outputs

**Ranked shortlist (top 10).** The full shortlist is in `outputs/ranked_shortlist.csv`. The top ten by PE attractiveness score are:

| Rank | Ticker | Company | PE Score | PE Acquired |
|---|---|---|---|---|
| 1 | PCTY | Paylocity Holding Corporation | 5.00 | No |
| 2 | DOCU | DocuSign, Inc. | 4.72 | No |
| 3 | ALRM | Alarm.com Holdings, Inc. | 4.64 | No |
| 4 | OKTA | Okta, Inc. | 4.62 | No |
| 5 | INST | Instructure Holdings, Inc. | 4.56 | **Yes** |
| 6 | DAY | Dayforce, Inc. | 4.54 | **Yes** |
| 7 | PAYC | Paycom Software, Inc. | 4.54 | No |
| 8 | APPF | AppFolio, Inc. | 4.48 | No |
| 9 | ZM | Zoom Communications, Inc. | 4.44 | No |
| 10 | WDAY | Workday, Inc. | 4.40 | No |

All five known PE-acquired companies with data completeness (INST, DAY, SQSP, PWSC, MODN) ranked within the top 18 of 28 evaluated companies, clustered in the mid-score range (3.72–4.56). This pattern is consistent with the buyout-fit thesis: genuine PE targets score well but not perfectly, because they possess improvement headroom rather than already-elite financial profiles.

**Sourcing memo (INST).** The Memo Agent produced a fully LLM-written sourcing memo for Instructure Holdings (see `outputs/memo_INST.md`). The memo opens with a company overview grounded in the business description, quantifies the key strengths (29.8 % FCF margin, 1.0x net debt/EBITDA, 11.6 % revenue growth), identifies the primary risks (9.3x EV/Revenue entry valuation, K-12 and higher education budget headwinds, competitive intensity in the edtech LMS market), proposes value-creation angles (margin expansion, bolt-on M&A using the available leverage capacity, go-to-market rationalisation), and closes with four specific next-diligence questions. The memo is coherent, financially grounded, and consistent with the deterministic subscores — it does not invent figures or contradict the scoring rationale. It is shorter and more formulaic than a real analyst memo would be, which is expected: the prompt asks for a screening memo from a constrained financial profile, not a full investment committee presentation.

## 8. Limitations

**Proxy ground truth.** The `pe_acquired` label is a lagging, incomplete proxy for buyout attractiveness. Companies without the label are not confirmed unattractive — they may simply not have received or completed a bid. This asymmetry inflates the apparent false-positive rate of any model. A more rigorous evaluation would require a held-out set of future acquisitions unseen at scoring time, which is a temporal splitting problem requiring a multi-year labelled dataset.

**Small universe with inflated base rate.** The 36-company universe was constructed by curating known PE take-privates alongside comparable public peers, producing an 11/36 base rate of 30.6 %. A production deployment would screen hundreds of companies with a base rate in the low single digits, which would substantially lower absolute Precision and NDCG values and place greater demands on the model's discrimination.

**Survivorship and hindsight labelling.** The positive labels were assigned with knowledge of which deals occurred. This is standard for a retrospective evaluation but means the scoring thresholds were tuned in the same universe they are evaluated against — there is no out-of-sample validation. A forward-looking test would require freezing the model and waiting for new acquisitions.

**Point-in-time data mismatch.** Positives (the eleven delisted PE-acquired companies) are scored on their last publicly available 10-K financials, which range from fiscal year 2021 to 2024 depending on the deal timeline. Negatives (still-listed companies) are scored on current `yfinance` data from 2024–2025. This temporal mismatch means the model is not making apples-to-apples comparisons: a currently-listed company whose metrics have deteriorated since 2022 would score lower today than it would have at the time the PE deals were actually being considered.

**Hand-set thresholds and weights.** All scoring thresholds and subscore weights in `config.py` were designed by the author based on qualitative understanding of LBO deal criteria, not learned from labelled data. They are transparent and auditable, which is a methodological virtue for this prototype, but they have not been validated against a large deal set. A logistic regression or gradient-boosting model trained on hundreds of historical take-privates could learn threshold values empirically and likely produce better-calibrated scores.

**Single-sector, single-geography universe.** The universe covers US-listed Software companies only. Sector-specific scoring criteria (e.g., the EV/Revenue thresholds appropriate for software SaaS businesses) may not transfer to industrials, healthcare, or consumer sectors without recalibration.

**LLM memo quality.** The Memo Agent uses `claude-haiku-4-5-20251001`, the lightest Anthropic model, for cost efficiency. Memo quality is adequate for a screening memo but constrained by both the model capability and the narrow financial profile provided as input. Real sourcing memos draw on earnings call transcripts, news, CRM data, and sector knowledge — none of which is available to this agent.

## 9. Future Work (conceptual — not implemented)
Clearly separated from the built system:
- Learned scoring (logistic regression / gradient boosting on a larger labelled
  deal set) replacing hand-set thresholds.
- RAG over filings and news with embeddings for richer qualitative signals.
- Larger, multi-sector, point-in-time universe with proper temporal splits.
- CRM / deal-flow integration; continuous monitoring for new candidates.
- Multimodal analysis (earnings-call transcripts, management commentary).
- Autonomous sourcing agents with memory and planning.

## 10. Conclusion

This paper presents a working, evaluated agentic AI framework for private equity deal sourcing in the software sector. The system demonstrates that a deterministic, rule-based scoring function built around the concept of *buyout fit* — as opposed to raw company quality — can surface verified PE acquisition targets above a market-cap baseline in a controlled evaluation setting. The pipeline placed two of eleven ground-truth PE acquisitions in the top ten (Instructure at rank 5, Dayforce at rank 6), achieving Precision@10 = 0.200 and NDCG@10 = 0.164 against a baseline of 0.000 on every metric.

The most consequential design decision was the v1→v2 scoring thesis correction. The initial model scored companies on raw financial quality, producing a ranking dominated by large, richly-valued software compounders that PE firms do not acquire. Reframing the objective as buyout fit — emphasising underwritable valuation, moderate growth, improvement headroom, and leverage capacity — was necessary to generate any signal at all. This correction is not a technical detail; it reflects a domain insight about how PE investment theses differ from equity portfolio construction.

The results are modest in absolute terms and the evaluation has structural limitations (small universe, proxy ground truth, temporal mismatch) documented in Section 8. The system is best understood as a methodology prototype that validates the approach and provides a reproducible baseline for extension. The clearest path to improvement is replacing hand-set thresholds with learned parameters trained on a larger, temporally split deal dataset — a direction enabled by the modular, auditable design of the current framework.

---

### Appendix A — How to reproduce
See `README.md`. `python main.py` then `python eval/evaluate.py`, with live data
(`rm data/cache.json` first).

### Appendix B — Implemented vs conceptual
**Implemented:** all five agents, data retrieval + caching, deterministic
scoring, LLM memo generation, ranked shortlist, full evaluation framework with
baseline comparison.
**Conceptual (Section 9 only):** learned scoring, RAG, multimodal analysis, CRM
integration, autonomous agents.
