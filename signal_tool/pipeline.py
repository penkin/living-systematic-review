"""The field map between the stages and stage 3 for one record.

`tags_for` shapes stage 1 and stage 2 output into an entry; `build_row` turns an entry
into one signals.csv row. Both are pure, so a reviewer's confirmation re-runs stage 3
from the stored entry and never repeats a model call.
"""

import csv

from signal_tool.geography import resolve
from signal_tool.scoring import score_record
from signal_tool.suggest import asked_fields

STAGE_ONE = (
    "record_type", "lane", "lane_reason", "recency_score", "is_duplicate", "duplicate_of",
    "secondary_report", "non_english", "countries_rule",
)
MODEL_META = ("model_version", "prompt_version", "prompt_date", "model_status", "validation_errors", "evidence_missing")
INPUT = ("record_id", "title", "abstract", "year", "language", "location")
# The stage 3 and geography columns, after the tagged fields.
SCORED = (
    "countries", "regions", "lmic_setting", "income_levels",
    "outcome_certainty", "n_studies",
)
TAIL = (
    "signal_score", "level_from_threshold", "signal_level",
    "override_triggered", "signal_reason", "suggested_action", "scope_question", "out_of_region",
    "model_status",
    "reviewer_decision", "reviewer_reason", "reviewer_initials", "reviewer_date",
    "rubric_version", "model_version", "prompt_version", "prompt_date", "reference_date",
)


def confirmable(rules):
    """The fields a human confirms or overrides on the record page. SPEC.md section 3."""
    return [f["id"] for f in rules["fields"] if f.get("confirmable")]


def columns(rules):
    """signals.csv columns: SPEC.md section 5 order, then the blank reviewer columns, then the version fields."""
    asked = [f["id"] for f in asked_fields(rules)]
    return (*INPUT, *STAGE_ONE, *asked, *SCORED, *rules["criteria"], *TAIL)


def model_meta(model):
    """The version and status fields of a validated stage 2 response, or unavailable."""
    if model is None:
        return {"model_status": "unavailable"}
    return {k: model.get(k) for k in MODEL_META}


def tags_for(record, model, rules):
    """One entry: stage 1 tags as rules, stage 2 tags as suggestions, plus the model meta."""
    tags = {f: {"value": record.get(f), "status": "rule", "evidence": ""} for f in STAGE_ONE}
    if model is not None:
        evidence = model.get("evidence") or {}
        for field in asked_fields(rules):
            key = field["id"]
            tags[key] = {"value": model.get(key), "status": "suggested", "evidence": evidence.get(key, "")}
    return {"tags": tags, "model": model_meta(model)}


def write_csv(rows, handle, rules):
    """signals.csv: every row in columns(rules) order, lists joined with semicolons."""
    writer = csv.DictWriter(handle, fieldnames=columns(rules), extrasaction="ignore")
    writer.writeheader()
    writer.writerows({k: _cell(v) for k, v in row.items()} for row in rows)


def _cell(value):
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return "" if value is None else value


def build_row(record, entry, review, rules, ref):
    """One signals.csv row: input fields, current tag values, geography, stage 3."""
    tags = {field: cell["value"] for field, cell in entry["tags"].items()}
    if entry["tags"]["record_type"]["status"] == "overridden":
        rule = rules["record_types"][tags["record_type"]]
        tags["lane"], tags["lane_reason"] = rule["lane"], rule.get("lane_reason", "")
    row = {k: record.get(k, "") for k in INPUT}
    row.update(tags)
    row.update({k: "" for k in columns(rules) if k not in row})
    row.update(entry["model"])
    row["rubric_version"] = rules["rubric_version"]
    row["reference_date"] = ref["date"]

    codes = set(tags.get("countries_rule") or []) | set(tags.get("countries_iso3") or [])
    geography = resolve(codes, ref, rules)
    row.update({k: geography[k] for k in ("countries", "country_names", "regions", "income_levels", "lmic_setting")})

    if tags["lane"] == "signal" and entry["model"]["model_status"] == "ok":
        row.update(score_record({**tags, **geography}, review, rules))
    return row
