"""Stage 1. Deterministic record typing, lane routing, geography, recency, duplicates."""

import re
from difflib import SequenceMatcher

import yaml

from signal_tool.geography import countries_in_text

# SPEC.md section 5: record_type comes from keyword markers on record_type_raw,
# title and abstract, in that order of authority.
SEARCH_FIELDS = ("record_type_raw", "title", "abstract")
GEOGRAPHY_FIELDS = ("title", "abstract", "location")


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


def _normalise_title(title, rules):
    text = (title or "").casefold()
    for prefix in rules["duplicates"]["strip_prefixes"]:
        text = text.removeprefix(prefix.casefold()).strip()
    # A preprint and its published version share the main title; the subtitle after
    # the colon changes between versions, so it is left out of the comparison.
    text = text.split(":", 1)[0]
    return re.sub(r"[^a-z\s]", "", text).strip()


def mark_duplicates(records, rules):
    """Flag in-batch duplicates by title similarity. A duplicate preprint leaves the lane."""
    threshold = rules["duplicates"]["title_similarity"]
    titles = [_normalise_title(r.get("title"), rules) for r in records]
    for record in records:
        record.setdefault("is_duplicate", False)
        record.setdefault("duplicate_of", "")
    # ponytail: O(n²) title compare, fine for a batch of hundreds
    for i, first in enumerate(records):
        for j in range(i + 1, len(records)):
            second = records[j]
            if SequenceMatcher(None, titles[i], titles[j]).ratio() < threshold:
                continue
            # The preprint is the copy. Between two like records, the later id is.
            loser, keeper = (first, second) if first["record_type"] == "preprint" else (second, first)
            loser["is_duplicate"] = True
            loser["duplicate_of"] = keeper["record_id"]
            if loser["record_type"] == "preprint" and loser["lane"] == "signal":
                loser["lane"] = "separate"
                loser["lane_reason"] = rules["duplicates"]["preprint_lane_reason"].format(
                    record_id=keeper["record_id"]
                )
    return records


def _year(value):
    match = re.search(r"\d{4}", str(value or ""))
    return int(match.group()) if match else None


def tag(records, rules, review=None, ref=None):
    """Add the stage 1 fields to each record. Returns the records."""
    for record in records:
        record["record_type"], record["lane"], record["lane_reason"] = classify(record, rules)
    mark_duplicates(records, rules)
    if review is None:
        return records

    low, high = review["update_window"]
    markers = [m.casefold() for m in rules["secondary_report_markers"]]
    for record in records:
        year = _year(record.get("year"))
        record["recency_score"] = int(year is not None and low <= year <= high)
        text = " ".join(record.get(f) or "" for f in GEOGRAPHY_FIELDS)
        record["countries_rule"] = countries_in_text(text, ref) if ref else []
        record["secondary_report"] = any(m in text.casefold() for m in markers)
        language = (record.get("language") or "").strip()
        record["non_english"] = bool(language) and language.casefold() != "english"
    return records
