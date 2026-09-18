"""Stage 2. One model call per record, closed lists in, validated JSON out.

Every value here is a suggestion until a human confirms it. The caller stores the
validated response with the record, so a confirmation never repeats the call.
"""

import json
import os
import urllib.request
from datetime import date

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
API_BASE = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
MODEL = os.environ.get("SIGNAL_MODEL", "anthropic/claude-haiku-4.5")
PROMPT_VERSION = "p3"
OUTCOME_NONE = "NONE"


def build_client():
    """``complete(system, user, schema) -> str`` when OPENROUTER_API_KEY is set, else None.

    The endpoint is OpenAI-compatible chat completions, so OPENROUTER_BASE_URL can point
    at any provider that speaks it. The demo runs on None.
    """
    if not API_KEY:
        return None

    def complete(system, user, schema):
        # Some OpenRouter models reject the strict json_schema format with a bare 400, so
        # the schema goes into the prompt and only json_object is enforced. validate() coerces.
        system = f"{system}\n\nReply with one JSON object matching this JSON schema:\n{json.dumps(schema)}"
        body = {
            "model": MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "max_tokens": 1024,
        }
        request = urllib.request.Request(
            f"{API_BASE}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)["choices"][0]["message"]["content"]

    return complete



def _evidence(fields):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(fields),
        "properties": {
            f: {
                "type": "string",
                "description": f"A short phrase copied verbatim from the title or abstract that supports {f}, "
                "or an empty string. Never repeat the value itself.",
            }
            for f in fields
        },
    }


def compile_prompt(review, rules):
    """The system text and the answer schema built from the rubric's `fields`.

    Only a field the model or the review supplies is asked for. `values` make a closed list,
    `type: list` takes several values, `type: number` an integer or null, else free text.
    """
    outcomes = [o["id"] for o in review["outcomes"]] + [OUTCOME_NONE]
    asked = asked_fields(rules)

    def shape(field):
        if field.get("source") == "review":
            return {"type": "string", "enum": outcomes}
        if field.get("type") == "number":
            return {"type": ["integer", "null"]}
        item = {"type": "string", "enum": list(field["values"])} if field.get("values") else {"type": "string"}
        return {"type": "array", "items": item} if field.get("type") == "list" else item

    ids = [f["id"] for f in asked]
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ids + ["evidence"],
        "properties": {**{f["id"]: shape(f) for f in asked}, "evidence": _evidence(ids)},
    }
    meanings = "\n".join(f"- {f['id']}: {f.get('prompt') or f['label']}" for f in asked)
    return _preamble(review) + meanings, schema


def asked_fields(rules):
    """The fields the model answers: every field the model or the review supplies."""
    return [f for f in rules["fields"] if f.get("source", "model") in ("model", "review")]


def _preamble(review):
    outcomes = "\n".join(f"- {o['id']}: {o['name']}" for o in review["outcomes"])
    return (
        "You tag one record for a living systematic review. You suggest; a human decides. "
        "Never include or exclude a study. Pick every value from the closed lists given. "
        "For each field copy one short phrase verbatim from the title or abstract into the "
        "matching evidence slot, or an empty string if nothing supports the value. The evidence "
        "is a quote from the text, never the value itself: "
        '{"study_design": "cohort", ..., "evidence": {"study_design": "We followed 2,340 pregnancies", ...}}. '
        "Answer in the JSON schema only.\n\n"
        f"Review question: {review['review_question'].strip()}\n\n"
        f"Outcomes the review tracks (use the id, or {OUTCOME_NONE} if none applies):\n{outcomes}\n\n"
        "Topics flagged out of scope (use NONE for these): "
        + "; ".join(review["out_of_scope_outcomes"])
        + "\n\nIntervention classes already in the review: "
        + "; ".join(review["intervention_classes_represented"])
        + "\n\nField meanings:\n"
    )


def record_text(record):
    """The user turn: the record's columns, record_id first so a fixture can find it."""
    return "\n".join(
        f"{k}: {record.get(k, '')}" for k in ("record_id", "title", "abstract", "record_type_raw", "location", "language")
    )


def parse_json(text):
    """The JSON object in a model reply, with any code fence or preamble stripped."""
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1] if start >= 0 else text)


def call_model(record, review, rules, client):
    system, schema = compile_prompt(review, rules)
    data = parse_json(client(system, record_text(record), schema))
    data.update(model_version=MODEL, prompt_version=PROMPT_VERSION, prompt_date=str(date.today()))
    return data


def validate(data, record, review, rules):
    """Coerce every answer onto its field's shape. A stray value becomes untagged (None) and is logged."""
    outcomes = {o["id"] for o in review["outcomes"]} | {OUTCOME_NONE}
    errors, missing = [], []

    def clean(field, value):
        allowed = set(outcomes if field.get("source") == "review" else field.get("values") or [])
        if field.get("type") == "number":
            return value if isinstance(value, int) and not isinstance(value, bool) else None
        if field.get("type") == "list":
            items = [v for v in value or [] if isinstance(v, str) and v and (not allowed or v in allowed)]
            return list(dict.fromkeys(items))
        if not allowed:
            return str(value or "")
        if value in allowed:
            return value
        errors.append(f"{field['id']}: {value!r}")
        return OUTCOME_NONE if field.get("source") == "review" else None

    out = dict(data)
    fields = asked_fields(rules)
    for field in fields:
        out[field["id"]] = clean(field, data.get(field["id"]))

    # The model sees the location column too and quotes it for countries; that is fair evidence.
    haystack = " ".join(record.get(k) or "" for k in ("title", "abstract", "location")).casefold()
    evidence = data.get("evidence") or {}
    out["evidence"] = {}
    for field in fields:
        phrase = str(evidence.get(field["id"]) or "")
        if phrase and phrase.casefold() not in haystack:
            missing.append(field["id"])
            phrase = ""
        out["evidence"][field["id"]] = phrase

    out["validation_errors"] = errors
    out["evidence_missing"] = missing
    out["model_status"] = "ok"
    return out


def suggest(record, review, rules, client):
    """Validated stage 2 tags for one record. Raises whatever the client raises."""
    return validate(call_model(record, review, rules, client), record, review, rules)
