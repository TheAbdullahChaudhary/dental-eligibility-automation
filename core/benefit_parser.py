import json
import os
import re
import boto3
from datetime import date, timedelta
from core.bob_report import BenefitFrequency

# Known frequency patterns — handle without AI to save cost/latency
FREQUENCY_PATTERNS = [
    (r"once every (\d+) months?",        lambda m: int(m.group(1))),
    (r"(\d+)x? per calendar year",       lambda m: 12 // int(m.group(1))),
    (r"twice per (?:calendar )?year",    lambda _: 6),
    (r"once per (?:calendar )?year",     lambda _: 12),
    (r"once every (\d+) years?",         lambda m: int(m.group(1)) * 12),
    (r"every (\d+) months?",             lambda m: int(m.group(1))),
]


def parse_frequency_locally(text: str) -> int | None:
    """Return interval in months if pattern is recognized, else None."""
    normalized = text.lower().strip()
    for pattern, extractor in FREQUENCY_PATTERNS:
        match = re.search(pattern, normalized)
        if match:
            return extractor(match)
    return None


def parse_frequency_with_ai(text: str) -> tuple[int | None, str]:
    """
    Use AWS Bedrock (Claude) to interpret ambiguous frequency text.
    Returns (months_interval, explanation).
    """
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

    prompt = (
        "You are a dental insurance expert. Given this benefit frequency description, "
        "return a JSON object with two fields:\n"
        "- 'months': integer interval in months (null if truly ambiguous)\n"
        "- 'note': brief explanation or flag if ambiguous\n\n"
        f"Frequency text: \"{text}\"\n\n"
        "Respond with JSON only."
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}]
    })

    response = client.invoke_model(modelId=model_id, body=body)
    result = json.loads(json.loads(response["body"].read())["content"][0]["text"])
    return result.get("months"), result.get("note", "")


def build_benefit(
    procedure_code: str,
    description: str,
    raw_frequency_text: str,
    last_service_date: date | None,
) -> BenefitFrequency:
    """Parse frequency and compute eligibility for a single benefit line."""
    months = parse_frequency_locally(raw_frequency_text)
    ai_note = None

    if months is None:
        months, ai_note = parse_frequency_with_ai(raw_frequency_text)

    next_eligible = None
    is_eligible = True

    if months and last_service_date:
        next_eligible = last_service_date + timedelta(days=months * 30)
        is_eligible = date.today() >= next_eligible

    return BenefitFrequency(
        procedure_code=procedure_code,
        description=description,
        raw_frequency_text=raw_frequency_text,
        normalized_months=months,
        last_service_date=last_service_date,
        next_eligible_date=next_eligible,
        is_eligible=is_eligible,
        notes=ai_note,
    )
