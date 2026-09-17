"""Stage 2. One cached model call per record, closed lists in, validated JSON out.

Every value here is a suggestion until a human confirms it. The cache is the demo:
a hit never touches the network, and a miss without a client leaves the record
visible with model_status "unavailable".
"""

import hashlib
import json
import os
import shutil
import urllib.request
from datetime import date
from pathlib import Path

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
API_BASE = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
MODEL = os.environ.get("SIGNAL_MODEL", "anthropic/claude-haiku-4.5")
PROMPT_VERSION = "p2"
OUTCOME_NONE = "NONE"

# field: (allowed_values list in review.yaml, safe default when the model strays)
CLOSED_FIELDS = {
    "study_design": ("study_design", "other"),
    "relevance": ("relevance", "Not relevant"),
    "intervention_tested": ("yes_no", "No"),
    "answers_question": ("yes_no", "No"),
    "harm_reported": ("yes_no_unclear", "Unclear"),
    "policy_relevance": ("policy_relevance", "None"),
}
EVIDENCE_FIELDS = (
    "study_design", "relevance", "outcome_touched", "intervention_tested", "answers_question",
    "equity_relevance", "harm_reported", "new_intervention_class", "policy_relevance",
    "countries_iso3", "sample_size",
)


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


def cache_key(record):
    digest = hashlib.sha256(((record.get("title") or "") + (record.get("abstract") or "")).encode("utf-8"))
    return f"{record['record_id']}-{digest.hexdigest()[:8]}.json"


def output_schema(review):
    values = review["allowed_values"]
    outcomes = [o["id"] for o in review["outcomes"]] + [OUTCOME_NONE]
    enum = lambda name: {"type": "string", "enum": list(values[name])}  # noqa: E731
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(EVIDENCE_FIELDS) + ["evidence"],
        "properties": {
            "study_design": enum("study_design"),
            "relevance": enum("relevance"),
            "outcome_touched": {"type": "string", "enum": outcomes},
            "intervention_tested": enum("yes_no"),
            "answers_question": enum("yes_no"),
            "equity_relevance": {
                "type": "object",
                "additionalProperties": False,
                "required": ["level", "factors"],
                "properties": {
                    "level": enum("equity_level"),
                    "factors": {"type": "array", "items": enum("progress_plus")},
                },
            },
            "harm_reported": enum("yes_no_unclear"),
            "new_intervention_class": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "class_name"],
                "properties": {"value": enum("yes_no"), "class_name": {"type": "string"}},
            },
            "policy_relevance": enum("policy_relevance"),
            "countries_iso3": {"type": "array", "items": {"type": "string"}},
            "sample_size": {"type": ["integer", "null"]},
            "evidence": {
                "type": "object",
                "additionalProperties": False,
                "required": list(EVIDENCE_FIELDS),
                "properties": {
                    f: {
                        "type": "string",
                        "description": f"A short phrase copied verbatim from the title or abstract that supports {f}, "
                        "or an empty string. Never repeat the value itself.",
                    }
                    for f in EVIDENCE_FIELDS
                },
            },
        },
    }


def build_prompt(record, review):
    """Return (system, user) text. The review supplies every list; nothing is hardcoded."""
    outcomes = "\n".join(f"- {o['id']}: {o['name']}" for o in review["outcomes"])
    system = (
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
        "- intervention_tested: Yes if the record evaluates an intervention.\n"
        "- answers_question: Yes if the record's result bears on the review question above.\n"
        "- equity_relevance.level: None, Group included (a PROGRESS-Plus group is in the sample), "
        "or Results by factor (results are reported by a PROGRESS-Plus factor).\n"
        "- harm_reported: Yes only if an adverse event or harm is a reported finding.\n"
        "- new_intervention_class.value: Yes if the record tests a class not in the list above.\n"
        "- policy_relevance: None, Some, or Direct (the record evaluates a policy or programme).\n"
        "- countries_iso3: ISO 3166 alpha-3 codes of the study countries.\n"
        "- sample_size: participants or units as an integer, or null."
    )
    user = (
        f"record_id: {record['record_id']}\n"
        f"title: {record.get('title', '')}\n"
        f"abstract: {record.get('abstract', '')}\n"
        f"record_type_raw: {record.get('record_type_raw', '')}\n"
        f"location: {record.get('location', '')}\n"
        f"language: {record.get('language', '')}"
    )
    return system, user


def parse_json(text):
    """The JSON object in a model reply, with any code fence or preamble stripped."""
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1] if start >= 0 else text)


def call_model(record, review, client):
    system, user = build_prompt(record, review)
    data = parse_json(client(system, user, output_schema(review)))
    data.update(model_version=MODEL, prompt_version=PROMPT_VERSION, prompt_date=str(date.today()))
    return data


def validate(data, record, review):
    """Coerce every value onto its closed list. Nothing is rejected; strays are logged."""
    values = review["allowed_values"]
    errors, missing = [], []

    def pick(field, value, list_name, default):
        if value in values[list_name]:
            return value
        errors.append(f"{field}: {value!r}")
        return default

    out = dict(data)
    for field, (list_name, default) in CLOSED_FIELDS.items():
        out[field] = pick(field, data.get(field), list_name, default)

    outcomes = {o["id"] for o in review["outcomes"]}
    if data.get("outcome_touched") not in outcomes | {OUTCOME_NONE}:
        errors.append(f"outcome_touched: {data.get('outcome_touched')!r}")
        out["outcome_touched"] = OUTCOME_NONE

    equity = data.get("equity_relevance") or {}
    out["equity_relevance"] = {
        "level": pick("equity_relevance.level", equity.get("level"), "equity_level", "None"),
        "factors": [f for f in equity.get("factors") or [] if f in values["progress_plus"]],
    }
    new_class = data.get("new_intervention_class") or {}
    out["new_intervention_class"] = {
        "value": pick("new_intervention_class.value", new_class.get("value"), "yes_no", "No"),
        "class_name": str(new_class.get("class_name") or ""),
    }
    out["countries_iso3"] = sorted(
        {c for c in data.get("countries_iso3") or [] if isinstance(c, str) and len(c) == 3 and c.isalpha()}
    )
    size = data.get("sample_size")
    out["sample_size"] = size if isinstance(size, int) and not isinstance(size, bool) else None

    # The model sees the location column too and quotes it for countries; that is fair evidence.
    haystack = " ".join(record.get(k) or "" for k in ("title", "abstract", "location")).casefold()
    evidence = data.get("evidence") or {}
    out["evidence"] = {}
    for field in EVIDENCE_FIELDS:
        phrase = str(evidence.get(field) or "")
        if phrase and phrase.casefold() not in haystack:
            missing.append(field)
            phrase = ""
        out["evidence"][field] = phrase

    out["validation_errors"] = errors
    out["evidence_missing"] = missing
    out["model_status"] = "ok"
    return out


def suggest(record, review, run_cache, shared_cache, client=None):
    """Cached, validated stage 2 tags for one record, or None when no cache and no client."""
    key = cache_key(record)
    run_path, shared_path = Path(run_cache) / key, Path(shared_cache) / key
    if not run_path.is_file():
        if shared_path.is_file():
            run_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shared_path, run_path)
        elif client is None:
            return None
        else:
            # The shared copy is what makes a record free on every later upload.
            text = json.dumps(call_model(record, review, client), indent=1)
            for path in (run_path, shared_path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    return validate(json.loads(run_path.read_text(encoding="utf-8")), record, review)
