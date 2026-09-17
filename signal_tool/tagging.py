"""Stage 1. Deterministic record typing and lane routing."""

import yaml

# SPEC.md section 5: record_type comes from keyword markers on record_type_raw,
# title and abstract, in that order of authority.
SEARCH_FIELDS = ("record_type_raw", "title", "abstract")


def load_rules(path):
    """Read the rules fresh every call, so an edit to rubric.yaml takes effect at once."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def classify(record, rules):
    """Return (record_type, lane, lane_reason) for one record."""
    for field in SEARCH_FIELDS:
        haystack = (record.get(field) or "").casefold()
        if not haystack:
            continue
        for name, rule in rules["record_types"].items():
            if any(marker.casefold() in haystack for marker in rule["markers"]):
                return name, rule["lane"], rule.get("lane_reason", "")

    default = rules["default_record_type"]
    rule = rules["record_types"][default]
    return default, rule["lane"], rule.get("lane_reason", "")


def tag(records, rules):
    """Add record_type, lane and lane_reason to each record. Returns the records."""
    for record in records:
        record["record_type"], record["lane"], record["lane_reason"] = classify(record, rules)
    return records
