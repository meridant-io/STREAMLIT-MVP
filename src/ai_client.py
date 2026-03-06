import os
import json
import time
import logging
from anthropic import Anthropic, APIStatusError

logger = logging.getLogger(__name__)

_client = None

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
MAX_RETRIES = int(os.getenv("ANTHROPIC_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("ANTHROPIC_RETRY_DELAY", "2.0"))


def get_ai_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment.")
        _client = Anthropic(api_key=api_key)
    return _client


def _call_with_retry(client: Anthropic, **kwargs):
    """Call client.messages.create with exponential backoff on 529 overload."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.messages.create(**kwargs)
        except APIStatusError as e:
            if e.status_code == 529 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Anthropic overloaded (529). Retry %d/%d in %.1fs",
                    attempt, MAX_RETRIES, delay,
                )
                time.sleep(delay)
            else:
                raise


def rank_capabilities_by_intent(
    intent_text: str,
    use_case_name: str,
    candidates: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """
    Send intent + candidate capabilities to Claude.
    Returns top_k capabilities ranked by relevance, each with an ai_score (0.0–1.0).

    Each candidate dict must have at minimum:
        capability_id, capability_name, domain_name, subdomain_name
    """
    client = get_ai_client()

    # Build a compact capability list for the prompt (avoid huge token counts)
    cap_list = "\n".join(
        f"{c['capability_id']}|{c['capability_name']}|{c['domain_name']}|{c['subdomain_name']}"
        for c in candidates
    )

    prompt = f"""You are an enterprise transformation consultant specialising in capability assessment.

A client has described the following use case and intent:

USE CASE: {use_case_name}
INTENT: {intent_text}

Below is a list of enterprise capabilities in the format:
capability_id|capability_name|domain|subdomain

{cap_list}

Your task:
1. Identify the {top_k} capabilities most directly relevant to achieving this intent.
2. Score each selected capability from 0.0 (not relevant) to 1.0 (highly relevant).
3. Return ONLY a JSON array with no preamble, no markdown, no explanation.

Each item in the array must have exactly these fields:
- capability_id (integer)
- capability_name (string)
- domain_name (string)
- subdomain_name (string)
- ai_score (float, 0.0 to 1.0)
- rationale (string, one sentence explaining why this capability is relevant)

Return exactly {top_k} items, sorted by ai_score descending.
"""

    response = _call_with_retry(
        client,
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    ranked = json.loads(raw)

    # Enrich with original candidate data (to preserve all fields downstream)
    cap_lookup = {c["capability_id"]: c for c in candidates}
    results = []
    for item in ranked:
        cid = int(item["capability_id"])
        base = cap_lookup.get(cid, {})
        merged = {**base, **item}
        merged["ai_score"] = float(item.get("ai_score", 0.0))
        merged["rationale"] = item.get("rationale", "")
        results.append(merged)

    return results
def generate_findings_narrative(
    use_case_name: str,
    intent_text: str,
    overall_score: float,
    domain_scores: list[dict],
    capability_scores: list[dict],
    high_risk_caps: list[dict],
    top_gaps: list[dict],
) -> str:
    """
    Uses Claude to generate a contextual executive findings narrative
    based on actual assessment scores and gaps.
    """
    client = get_ai_client()

    domain_summary = "\n".join(
        f"- {d['domain']}: {d['avg_score']}/5 (target: {d.get('target', 3)}, gap: {d['gap']})"
        for d in sorted(domain_scores, key=lambda x: x["avg_score"])
    )

    high_risk_summary = "\n".join(
        f"- {c['capability_name']} ({c['domain']}, {c['capability_role']}): {c['avg_score']}/5"
        for c in high_risk_caps
    ) if high_risk_caps else "None"

    gap_summary = "\n".join(
        f"- {c['capability_name']} ({c['domain']}): gap of {c['gap']:.1f}"
        for c in top_gaps
    ) if top_gaps else "None"

    cap_count = len(capability_scores)
    domain_count = len(domain_scores)

    prompt = f"""You are a senior enterprise transformation consultant writing an executive assessment findings report.

The following capability assessment has been completed:

USE CASE: {use_case_name}
INTENT: {intent_text}
OVERALL MATURITY SCORE: {overall_score}/5
CAPABILITIES ASSESSED: {cap_count}
DOMAINS COVERED: {domain_count}

DOMAIN SCORES (lowest to highest):
{domain_summary}

HIGH RISK CAPABILITIES (score below 2):
{high_risk_summary}

TOP CAPABILITY GAPS (largest gap to target of 3):
{gap_summary}

Write a professional executive summary of 3–4 paragraphs that:
1. Opens with an overall assessment of maturity relative to the use case intent
2. Highlights the strongest and weakest domains with specific observations
3. Calls out high-risk capabilities and what this means for the transformation
4. Closes with 3 prioritised recommendations for immediate action

Write in a direct, professional consulting tone suitable for a CIO or executive sponsor.
Do not use bullet points — write in flowing paragraphs.
Do not repeat the raw numbers mechanically — interpret what they mean.
"""

    response = _call_with_retry(
        client,
        model=DEFAULT_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()