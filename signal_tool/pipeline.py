"""Runs the three stages for one run directory and writes tags.json and signals.csv.

Stages 1 and 2 run once, in `run`. Stage 3 re-runs from tags.json alone in `rescore`,
so a reviewer's confirmation never repeats a model call.
"""

import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from signal_tool.geography import resolve
from signal_tool.scoring import score_record
from signal_tool.suggest import suggest
from signal_tool.tagging import tag

# SPEC.md section 3: the five fields a human confirms or overrides.
CONFIRMABLE = ("record_type", "relevance", "outcome_touched", "harm_reported", "new_intervention_class")

STAGE_ONE = (
    "record_type", "lane", "lane_reason", "recency_score", "is_duplicate", "duplicate_of",
    "secondary_report", "non_english", "countries_rule",
)
# stage 2 field name in tags -> (key in the model JSON, evidence key)
STAGE_TWO = {
    "study_design": ("study_design", "study_design"),
    "relevance": ("relevance", "relevance"),
    "outcome_touched": ("outcome_touched", "outcome_touched"),
    "intervention_tested": ("intervention_tested", "intervention_tested"),
    "answers_question": ("answers_question", "answers_question"),
    "equity_level": (("equity_relevance", "level"), "equity_relevance"),
    "equity_factors": (("equity_relevance", "factors"), "equity_relevance"),
    "harm_reported": ("harm_reported", "harm_reported"),
    "new_intervention_class": (("new_intervention_class", "value"), "new_intervention_class"),
    "new_class_name": (("new_intervention_class", "class_name"), "new_intervention_class"),
    "policy_relevance": ("policy_relevance", "policy_relevance"),
    "countries_iso3": ("countries_iso3", "countries_iso3"),
    "sample_size": ("sample_size", "sample_size"),
}
MODEL_META = ("model_version", "prompt_version", "prompt_date", "model_status", "validation_errors", "evidence_missing")

# SPEC.md section 5 order, then the blank reviewer columns, then the version fields.
COLUMNS = (
    "record_id", "title", "abstract", "year", "language", "location",
    *STAGE_ONE,
    "study_design", "relevance", "outcome_touched", "intervention_tested", "answers_question",
    "equity_level", "equity_factors", "harm_reported", "new_intervention_class", "new_class_name",
    "policy_relevance", "sample_size",
    "countries", "regions", "lmic_setting",
    "outcome_certainty", "n_studies",
    "A", "B", "C", "D", "E", "F", "G", "signal_score", "level_from_threshold", "signal_level",
    "override_triggered", "signal_reason", "suggested_action", "scope_question", "out_of_region",
    "model_status",
    "reviewer_decision", "reviewer_reason", "reviewer_initials", "reviewer_date",
    "rubric_version", "model_version", "prompt_version", "prompt_date", "reference_date",
)


def read_cards(run_dir):
    with (Path(run_dir) / "cards.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_tags(run_dir):
    return json.loads((Path(run_dir) / "tags.json").read_text(encoding="utf-8"))


def write_tags(run_dir, tagged):
    (Path(run_dir) / "tags.json").write_text(json.dumps(tagged, indent=1), encoding="utf-8")


def _dig(data, key):
    if isinstance(key, tuple):
        return (data.get(key[0]) or {}).get(key[1])
    return data.get(key)


def _tags_for(record, model):
    tags = {f: {"value": record.get(f), "status": "rule", "evidence": ""} for f in STAGE_ONE}
    meta = {"model_status": "unavailable"}
    if model is not None:
        evidence = model.get("evidence") or {}
        for field, (key, evidence_key) in STAGE_TWO.items():
            tags[field] = {"value": _dig(model, key), "status": "suggested", "evidence": evidence.get(evidence_key, "")}
        meta = {k: model.get(k) for k in MODEL_META}
    return {"tags": tags, "model": meta}


def run(run_dir, review, rules, ref, shared_cache, client=None):
    """Stages 1 to 3 for a fresh upload. Writes tags.json and signals.csv."""
    run_dir = Path(run_dir)
    records = tag(read_cards(run_dir), rules, review, ref)
    # Separate-lane records are tagged too, so a record_type override can still score
    # without a second model call. One call per record keeps the cache per record; the
    # calls run side by side because a single call takes tens of seconds.
    workers = int(os.environ.get("SIGNAL_CONCURRENCY", "8"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        models = list(pool.map(lambda r: suggest(r, review, run_dir / "model", shared_cache, client), records))
    tagged = {record["record_id"]: _tags_for(record, model) for record, model in zip(records, models)}
    write_tags(run_dir, tagged)
    return rescore(run_dir, review, rules, ref)


def build_rows(run_dir, review, rules, ref):
    """Stage 3 for every record, from tags.json. Writes nothing."""
    tagged = read_tags(run_dir)
    return [build_row(record, tagged[record["record_id"]], review, rules, ref) for record in read_cards(run_dir)]


def rescore(run_dir, review, rules, ref):
    """Stage 3 only, from tags.json. Rewrites signals.csv and returns the rows."""
    run_dir = Path(run_dir)
    rows = build_rows(run_dir, review, rules, ref)
    with (run_dir / "signals.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: _cell(v) for k, v in row.items()} for row in rows)
    return rows


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
    row = {k: record.get(k, "") for k in ("record_id", "title", "abstract", "year", "language", "location")}
    row.update(tags)
    row.update({k: "" for k in COLUMNS if k not in row})
    row.update(entry["model"])
    row["rubric_version"] = rules["rubric_version"]
    row["reference_date"] = ref["date"]

    codes = set(tags.get("countries_rule") or []) | set(tags.get("countries_iso3") or [])
    geography = resolve(codes, ref, rules)
    row.update({k: geography[k] for k in ("countries", "country_names", "regions", "lmic_setting")})

    if tags["lane"] == "signal" and entry["model"]["model_status"] == "ok":
        row.update(score_record({**tags, **geography}, review, rules))
    return row
