import json
from dataclasses import dataclass
from src.ai_client import get_ai_client, _call_with_retry, DEFAULT_MODEL


@dataclass
class Question:
    use_case: str
    capability_id: int
    capability_name: str
    domain: str
    subdomain: str
    capability_role: str
    question: str
    response_type: str
    guidance: str


def generate_questions_for_capability(
    use_case: str,
    cap: dict,
    role: str,
    questions_per_capability: int = 4,
    style: str = "Maturity (1–5)",
) -> list[Question]:
    """
    Uses Claude to generate contextual assessment questions for a capability.
    """
    client = get_ai_client()

    # Map style to response_type and guidance instruction
    style_map = {
        "Maturity (1–5)": (
            "maturity_1_5",
            "Score 1–5: 1=Not Defined, 2=Informal, 3=Defined, 4=Governed, 5=Optimized",
            "Each question should ask how consistently or maturely this capability is implemented. "
            "Frame questions to elicit a score from 1 (not defined) to 5 (optimized)."
        ),
        "Evidence (Yes/No + notes)": (
            "yes_no_evidence",
            "Answer Yes / No / Partial and provide supporting evidence or notes.",
            "Each question should ask whether something exists, is defined, or is in place. "
            "Frame as Yes/No questions that invite evidence (e.g. 'Is there a defined policy for...?')."
        ),
        "Workshop (discussion)": (
            "free_text",
            "Discuss openly and capture key points from the group.",
            "Each question should be open-ended and discussion-oriented, suitable for a workshop setting. "
            "Frame to draw out current state, pain points, and aspirations."
        ),
    }

    response_type, guidance, style_instruction = style_map.get(
        style, style_map["Maturity (1–5)"]
    )

    prompt = f"""You are an enterprise transformation consultant conducting a capability assessment.

USE CASE: {use_case}
CAPABILITY: {cap['capability_name']}
DOMAIN: {cap['domain_name']}
SUBDOMAIN: {cap['subdomain_name']}
ROLE IN ASSESSMENT: {role} (Core = directly relevant, Upstream = prerequisite/enabler, Downstream = outcome/consumer)

Generate exactly {questions_per_capability} assessment questions for this capability.

Style instruction: {style_instruction}

Requirements:
- Questions must be specific to this capability and domain — not generic
- Questions must be relevant to the use case context
- Each question should assess a different dimension (e.g. ownership, process maturity, tooling, governance, measurement)
- For {role} capabilities, adjust depth accordingly:
  - Core: deep, detailed questions about current state and maturity
  - Upstream: focus on whether foundations and enablers are in place
  - Downstream: focus on whether outcomes and value are being realised

Return ONLY a JSON array with no preamble, no markdown, no explanation.
Each item must have exactly these fields:
- question (string)
- guidance (string, one sentence coaching the assessor on what to look for)

Return exactly {questions_per_capability} items.
"""

    response = _call_with_retry(
        client,
        model=DEFAULT_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    items = json.loads(raw)

    questions = []
    for item in items:
        questions.append(Question(
            use_case=use_case,
            capability_id=int(cap["capability_id"]),
            capability_name=cap["capability_name"],
            domain=cap["domain_name"],
            subdomain=cap["subdomain_name"],
            capability_role=role,
            question=item["question"],
            response_type=response_type,
            guidance=item["guidance"],
        ))

    return questions