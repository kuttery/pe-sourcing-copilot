"""
agents/memo_agent.py

Memo Generation Agent — Step 4 of the pipeline.

This is the one genuinely LLM-powered agent. For each top-K company it
feeds the structured profile + deterministic subscores into Claude and
asks for a short, structured PE sourcing memo.

Design notes:
  - The LLM only WRITES (synthesises a memo). It never SCORES — scoring
    stays deterministic and auditable in scoring_agent.py.
  - Requires the ANTHROPIC_API_KEY environment variable.
  - If the key is absent, the agent degrades gracefully: it emits a
    clearly-labelled template memo so the rest of the pipeline still runs.
    This makes the system testable without a key, but a real run with a
    key produces the genuine LLM memos.
"""
import os
from config import MEMO_MODEL


def _load_dotenv():
    """Load ANTHROPIC_API_KEY from a .env file, overriding any empty env var."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return  # already set to a non-empty value — nothing to do
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip().strip('"').strip("'")


_load_dotenv()

MEMO_SECTIONS = [
    "Company Overview",
    "Why It May Be Attractive for PE",
    "Key Strengths",
    "Key Risks",
    "Possible Value-Creation Angles",
    "Next Diligence Questions",
]


def _build_prompt(profile: dict, score: dict) -> str:
    """Assemble the user prompt for one company."""
    subs = "\n".join(
        f"  - {k}: {v}/5  ({score['rationales'].get(k, '')})"
        for k, v in score["subscores"].items()
    )
    desc = (profile.get("description") or "No description available.")[:1200]
    return f"""You are a private equity analyst writing a first-pass sourcing memo.

COMPANY: {profile.get('company_name')} ({profile.get('ticker')})
INDUSTRY: {profile.get('industry') or 'n/a'}

BUSINESS DESCRIPTION:
{desc}

KEY FINANCIALS:
  - Market cap: {profile.get('market_cap')}
  - Revenue: {profile.get('revenue')}
  - EBITDA margin: {profile.get('ebitda_margin')}
  - FCF margin: {profile.get('fcf_margin')}
  - Revenue growth: {profile.get('revenue_growth')}
  - Net debt / EBITDA: {profile.get('net_debt_ebitda')}
  - EV / Revenue: {profile.get('ev_revenue')}

DETERMINISTIC PE ATTRACTIVENESS SCORE: {score['pe_score']}/5
SUBSCORES:
{subs}

Write a concise PE sourcing memo with exactly these sections:
{chr(10).join('  ' + s for s in MEMO_SECTIONS)}

Keep each section to 2-4 sentences. Be specific and tie observations to the
financials above. Do not invent numbers not given. This is a screening memo,
not investment advice."""


def _template_memo(profile: dict, score: dict) -> str:
    """Fallback memo used when no API key is available."""
    lines = [
        f"# Sourcing Memo (TEMPLATE — no API key) — {profile.get('company_name')}",
        "",
        "*This is a fallback template generated without an LLM call. "
        "Set ANTHROPIC_API_KEY and re-run to get the full memo.*",
        "",
        f"**PE Attractiveness Score:** {score['pe_score']}/5",
        "",
    ]
    for section in MEMO_SECTIONS:
        lines.append(f"## {section}")
        lines.append("_(LLM-generated content appears here on a real run.)_")
        lines.append("")
    lines.append("### Subscores")
    for k, v in score["subscores"].items():
        lines.append(f"- {k}: {v}/5 — {score['rationales'].get(k, '')}")
    return "\n".join(lines)


def _call_claude(prompt: str) -> str:
    """Call the Anthropic API. Raises if key/library missing."""
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=MEMO_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def run(profiles: dict, scores: dict, top_tickers: list) -> dict:
    """Generate a memo for each ticker in top_tickers.

    Returns ticker -> memo markdown string.
    """
    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not have_key:
        print("[MemoAgent] WARNING: ANTHROPIC_API_KEY not set — "
              "emitting TEMPLATE memos. Set the key and re-run for real memos.")

    memos = {}
    for ticker in top_tickers:
        profile = profiles[ticker]
        score = scores[ticker]
        if have_key:
            try:
                print(f"  [MemoAgent] generating memo for {ticker} ...")
                body = _call_claude(_build_prompt(profile, score))
                memos[ticker] = f"# Sourcing Memo — {profile.get('company_name')} ({ticker})\n\n{body}"
            except Exception as e:
                print(f"  [MemoAgent] ERROR for {ticker} ({e}); using template")
                memos[ticker] = _template_memo(profile, score)
        else:
            memos[ticker] = _template_memo(profile, score)

    print(f"[MemoAgent] produced {len(memos)} memos "
          f"({'LLM' if have_key else 'template'} mode)")
    return memos


if __name__ == "__main__":
    print("memo_agent module OK; run via main.py")
