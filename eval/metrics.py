"""
eval/metrics.py

Evaluation framework for the PE Sourcing Copilot.

Treats PE deal sourcing as a ranking / information-retrieval problem:
given a ranked shortlist of candidate targets, how many of the companies
that PE firms ACTUALLY took private appear near the top?

Ground truth: the `pe_acquired` column in data/universe.csv — companies
verified (via public reporting) to have been taken private by PE/buyout
firms. This is a PROXY for "attractive target": a still-public company is
not necessarily unattractive, it simply has not been acquired. This
limitation is stated explicitly in the report.

Metrics implemented:
  - Precision@K : fraction of the top-K that are true positives
  - Recall@K    : fraction of all true positives captured in the top-K
  - NDCG@K      : ranking quality, rewards placing positives higher
"""
import math


def precision_at_k(ranked_tickers, labels, k):
    """Fraction of top-k that are positives."""
    topk = ranked_tickers[:k]
    if not topk:
        return 0.0
    hits = sum(labels.get(t, 0) for t in topk)
    return hits / len(topk)


def recall_at_k(ranked_tickers, labels, k):
    """Fraction of all positives that appear in top-k."""
    total_pos = sum(labels.values())
    if total_pos == 0:
        return 0.0
    topk = ranked_tickers[:k]
    hits = sum(labels.get(t, 0) for t in topk)
    return hits / total_pos


def ndcg_at_k(ranked_tickers, labels, k):
    """Normalised Discounted Cumulative Gain at k.

    Binary relevance (1 = PE-acquired, 0 = not). DCG discounts gains by
    log2 of rank position; IDCG is the best achievable DCG. NDCG = DCG/IDCG.
    """
    topk = ranked_tickers[:k]
    dcg = 0.0
    for i, t in enumerate(topk):
        rel = labels.get(t, 0)
        dcg += rel / math.log2(i + 2)  # i+2 because rank 1 -> log2(2)=1

    total_pos = sum(labels.values())
    ideal_hits = min(total_pos, k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    return (dcg / idcg) if idcg > 0 else 0.0


def evaluate_ranking(ranked_tickers, labels, k_values):
    """Compute all metrics at every k. Returns a nested dict."""
    out = {}
    for k in k_values:
        out[k] = {
            "precision": round(precision_at_k(ranked_tickers, labels, k), 3),
            "recall": round(recall_at_k(ranked_tickers, labels, k), 3),
            "ndcg": round(ndcg_at_k(ranked_tickers, labels, k), 3),
        }
    return out


if __name__ == "__main__":
    # self-test: perfect ranking should score 1.0 precision/ndcg at small k
    labels = {"A": 1, "B": 1, "C": 0, "D": 0, "E": 1}
    perfect = ["A", "B", "E", "C", "D"]
    worst = ["C", "D", "A", "B", "E"]
    print("perfect:", evaluate_ranking(perfect, labels, [3]))
    print("worst:  ", evaluate_ranking(worst, labels, [3]))
