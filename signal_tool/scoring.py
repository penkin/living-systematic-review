"""Stage 3. Certainty lookup, criteria A–G, overrides, threshold, reason.

Pure. No model call, no network. A reviewer who overrides a tag re-runs this, so it
must stay cheap and callable without an HTTP request.
"""

from signal_tool.suggest import OUTCOME_NONE

REASON_WORD_LIMIT = 15


def score(criterion, value, rules):
    """Score one criterion from the value of its source field."""
    rule = rules["criteria"][criterion]
    return rule["scores"].get(value, rule["default"])


def score_from_tags(criterion, tags, rules):
    rule = rules["criteria"][criterion]
    if rule.get("zero_when_true") and tags.get(rule["zero_when_true"]):
        return 0
    if "parts" in rule:
        return sum(part["scores"].get(tags.get(part["source_field"]), 0) for part in rule["parts"])
    return score(criterion, tags.get(rule["source_field"]), rules)


def lookup_certainty(outcome_id, review):
    """The review's own certainty and study count. Looked up, never judged."""
    for outcome in review["outcomes"]:
        if outcome["id"] == outcome_id:
            return outcome
    return None


def _cap(level, cap, levels):
    return levels[min(levels.index(level), levels.index(cap))]


def _setting(tags):
    names = tags.get("country_names") or []
    if not names:
        return "unclear setting"
    if len(names) <= 2:
        return " and ".join(names)
    return f"{len(names)} countries"


def _reason(fields, rules):
    prefix = rules["reason_override_prefix"]
    override = f"{prefix} {fields['override']}." if fields["override"] else ""
    templates = [rules["reason_template_scope"]] if fields["scope_question"] else [
        rules["reason_template"], rules["reason_template_short"]
    ]
    # The override is the clause a reviewer must see, so every template is tried
    # with it before any template drops it.
    candidates = [t.format(**{**fields, "override": override}) for t in templates]
    candidates += [t.format(**{**fields, "override": ""}) for t in templates]
    for text in candidates:
        text = " ".join(text.split())
        if len(text.split()) <= REASON_WORD_LIMIT:
            return text
    return " ".join(candidates[-1].split()[:REASON_WORD_LIMIT])


def score_record(tags, review, rules):
    """Criteria, total, level, override and reason for one signal-lane record."""
    levels = rules["levels"]
    outcome_id = tags.get("outcome_touched") or OUTCOME_NONE
    outcome = lookup_certainty(outcome_id, review)
    scope_question = outcome is None
    certainty = outcome["certainty"] if outcome else ""
    n_studies = outcome["n_studies"] if outcome else 0

    scores = {c: score_from_tags(c, tags, rules) for c in "ABCDEF"}
    # SPEC.md section 4: an outcome the review does not cover, or one the table has
    # decided not to pursue, earns nothing for landing where the review is uncertain.
    if scope_question or outcome.get("certainty_inverted"):
        scores["G"] = 0
    else:
        scores["G"] = score_from_tags("G", {"outcome_certainty": certainty}, rules)
    total = sum(scores.values())

    high, moderate = rules["thresholds"]["high"], rules["thresholds"]["moderate"]
    if total >= high["min_total"] and scores["A"] >= high["min_A"]:
        level = "HIGH"
    elif total >= moderate["min_total"]:
        level = "MODERATE"
    else:
        level = "LOW"
    a_cap = rules["thresholds"]["a_caps"].get(scores["A"])
    if a_cap:
        level = _cap(level, a_cap, levels)
    level_from_threshold = level

    switches = rules["switches"]
    if scope_question and switches["out_of_scope_handling"] == "suppress":
        level = "LOW"

    regions = set(tags.get("regions") or [])
    in_scope = set(review.get("in_scope_regions") or [])
    out_of_region = bool(regions and in_scope and not regions & in_scope)
    if out_of_region and switches["out_of_region_cap"] != "none":
        level = _cap(level, switches["out_of_region_cap"], levels)

    size = tags.get("sample_size")
    if (
        switches["promote_large_studies_on_moderate"]
        and level == "MODERATE"
        and certainty == "Moderate"
        and isinstance(size, int)
        and size >= switches["large_study_n"]
    ):
        level = "HIGH"

    geography = set(tags.get("countries") or []) | regions
    absent = set(outcome.get("absent_contexts") or []) if outcome else set()
    tags = dict(tags, absent_context_hit="Yes" if geography & absent else "No")

    triggered = []
    if scores["A"] > 0:
        for rule in rules["overrides"]:
            if tags.get(rule["source_field"]) != rule["equals"]:
                continue
            triggered.append(rule)
            if rule["action"] == "raise":
                level = levels[min(levels.index(level) + 1, len(levels) - 1)]
            else:
                level = rule["action"]

    reason = _reason(
        {
            "design": rules["design_labels"].get(tags.get("study_design"), rules["design_labels"]["other"]),
            "setting": _setting(tags),
            "outcome": outcome.get("short", outcome["name"]) if outcome else "",
            "n_studies": n_studies,
            "studies": "study" if n_studies == 1 else "studies",
            "certainty": certainty.lower(),
            "override": ", ".join(r["label"] for r in triggered),
            "scope_question": scope_question,
        },
        rules,
    )
    return {
        **scores,
        "signal_score": total,
        "level_from_threshold": level_from_threshold,
        "override_triggered": ";".join(r["name"] for r in triggered),
        "signal_level": level,
        "suggested_action": rules["suggested_action"][level],
        "signal_reason": reason,
        "outcome_certainty": certainty,
        "n_studies": n_studies,
        "scope_question": scope_question,
        "out_of_region": out_of_region,
        "absent_context_hit": tags["absent_context_hit"],
    }
