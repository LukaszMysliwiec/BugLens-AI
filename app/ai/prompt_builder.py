"""Prompt engineering for BugLens AI analysis.

Design principles:
1. Ground every prompt in *real* test results – no generic advice.
2. Limit input to structured JSON (never raw HTML) to control token usage.
3. Instruct the model to be concrete and reference specific detected elements.
4. Use a strict JSON output schema to prevent hallucination drifting into prose.
"""

from __future__ import annotations

import json

from app.models.schemas import PageElements, TestResult

# ---------------------------------------------------------------------------
# Output size caps (keep in sync with the system prompt below)
# ---------------------------------------------------------------------------
MAX_INSIGHTS = 8
MAX_TEST_SUGGESTIONS = 5
MAX_UX_RECOMMENDATIONS = 5

# ---------------------------------------------------------------------------
# System prompt – sets the persona and output contract
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""You are a senior QA engineer and web accessibility specialist.
You are given structured data extracted from a real web page along with the results of automated QA tests.
Your job is to produce a concise, actionable analysis report in valid JSON.

Rules:
- Base every insight ONLY on the data provided. Do NOT invent issues not present in the data.
- Be specific: reference element counts, URLs, missing attributes by name.
- Do NOT repeat the same recommendation multiple times.
- Respond ONLY with a JSON object matching the schema below – no markdown fences, no prose outside JSON.

Output schema:
{{
  "summary": "<2-3 sentence plain-English summary of the overall page quality>",
  "insights": [
    {{
      "category": "<accessibility|seo|performance|security|ux>",
      "severity": "<critical|high|medium|low|info>",
      "issue": "<concrete description of the problem>",
      "recommendation": "<concrete, actionable fix>",
      "affected_element": "<optional – tag/selector/url that is affected>"
    }}
  ],
  "test_suggestions": ["<next automated test to write>", ...],
  "ux_recommendations": ["<specific UX improvement>", ...]
}}

Keep insights list to a maximum of {MAX_INSIGHTS} items. Keep test_suggestions to a maximum of {MAX_TEST_SUGGESTIONS}. Keep ux_recommendations to a maximum of {MAX_UX_RECOMMENDATIONS}.
"""


def _serialize_test_results(results: list[TestResult]) -> list[dict]:
    """Convert TestResult objects to a compact dict representation."""
    return [
        {
            "check": r.check_name,
            "status": r.status.value,
            "severity": r.severity.value,
            "description": r.description,
            "details": r.details,
        }
        for r in results
    ]


def _serialize_page_elements(elements: PageElements) -> dict:
    """Compact representation of PageElements for AI consumption."""
    return {
        "url": elements.url,
        "title": elements.title,
        "meta_description": elements.meta_description,
        "has_viewport_meta": elements.has_viewport_meta,
        "form_count": len(elements.forms),
        "forms": [
            {
                "action": f.action,
                "method": f.method,
                "field_count": len(f.fields),
                "has_password_field": any(fld.input_type == "password" for fld in f.fields),
                "fields": [
                    {"name": fld.name, "type": fld.input_type, "required": fld.required}
                    for fld in f.fields
                ],
            }
            for f in elements.forms
        ],
        "button_count": len(elements.buttons),
        "buttons": elements.buttons[:10],
        "link_count": len(elements.links),
        "external_link_count": sum(1 for l in elements.links if l.is_external),
        "images_without_alt_count": len(elements.images_without_alt),
        "images_without_alt_sample": elements.images_without_alt[:5],
        "heading_structure": elements.heading_structure[:15],
    }


def build_user_prompt(elements: PageElements, test_results: list[TestResult]) -> str:
    """Build the user-turn message that grounds the AI in real data."""
    payload = {
        "page_elements": _serialize_page_elements(elements),
        "test_results": _serialize_test_results(test_results),
    }
    return (
        "Analyze the following web page QA data and produce your JSON report.\n\n"
        + json.dumps(payload, indent=2)
    )
