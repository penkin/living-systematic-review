"""The rubric builder form over rubric.yaml and review.yaml.

The form starts from a pair of dicts, the files on disk or a stored YAML text, and writes its
values over them. Everything the form does not show stays as the starting point holds it.
"""

import copy
import re

import yaml

from signal_tool.geography import REGION_COLUMNS

# ponytail: record types, duplicates, level names, reason templates and the hand sheet are not
# the form. Add a section here and in rubric_detail.html when the team needs to change one.

OUTCOME_FIELDS = ("id", "name", "short", "n", "certainty", "absent", "inverted")
FIELD_COLUMNS = ("id", "label", "values", "prompt", "confirmable", "type")
# How a model field is answered: one value from the list or free text, several values, or an integer.
FIELD_TYPES = {"": "One value", "list": "Several values", "number": "A number"}
CRITERION_COLUMNS = ("index", "id", "name", "help", "max", "default")
OVERRIDE_COLUMNS = ("name", "label", "field", "equals", "action")
# The keys of a criterion the score rows rebuild; every other key is carried from the base criterion.
SCORE_KEYS = ("source_field", "scores", "default", "value_labels", "parts")
ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
NUMBER_ERROR = "Every points, threshold and count box needs a whole number."


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        # design_labels is an anchor shared by criterion D; a copy reads better than &id001.
        return True


def dump(data):
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True)


def field_values(field, review):
    """The closed list of one field: the review's outcomes for the outcome pick, else the field's own list."""
    if field.get("source") == "review":
        return [o["id"] for o in review["outcomes"]]
    return field.get("values", [])


def _score_rows(rule):
    parts = rule.get("parts") or [rule]
    return [(part["source_field"], value, points) for part in parts for value, points in part["scores"].items()]


def _certainties(rules):
    """The certainty levels an outcome can have: the values of the built-in `outcome_certainty` field."""
    return next(f["values"] for f in rules["fields"] if f["id"] == "outcome_certainty")


def form_context(review, rules, ref):
    fields = [
        {
            **f,
            "editable": f.get("source", "model") == "model",
            "values_text": ", ".join(str(v) for v in field_values(f, review)),
        }
        for f in rules["fields"]
    ]
    criteria = [
        {
            "id": c,
            "name": r["name"],
            "help": r["help"],
            "max": r["max"],
            "default": r.get("default", 0),
            "rows": _score_rows(r),
        }
        for c, r in rules["criteria"].items()
    ]
    levels = list(reversed(rules["levels"]))
    regions = sorted({row[col] for row in ref["countries"].values() for col in REGION_COLUMNS if row.get(col)})
    outcomes = [
        {
            "id": o["id"],
            "name": o["name"],
            "short": o.get("short", ""),
            "n_studies": o["n_studies"],
            "certainty": o["certainty"],
            "absent": ", ".join(o.get("absent_contexts") or []),
            "inverted": bool(o.get("certainty_inverted")),
        }
        for o in review["outcomes"]
    ]
    return {
        "fields": fields,
        "field_types": FIELD_TYPES,
        "field_options": [(f["id"], f["label"]) for f in rules["fields"]],
        "rubric_version": rules["rubric_version"],
        "levels": [(level, rules["suggested_action"][level]) for level in levels],
        "level_ids": levels,
        "thresholds": rules["thresholds"],
        "a_caps": sorted(rules["thresholds"]["a_caps"].items()),
        "criteria": criteria,
        "overrides": rules["overrides"],
        "override_effects": rules["level_steps"]["override_effects"],
        "switches": rules["switches"],
        "income_groups": [(k, label, k in rules["lmic_income_levels"]) for k, label in rules["income_labels"].items()],
        "regret_top_n": rules["regret_top_n"],
        "review_id": review["review_id"],
        "review_question": review["review_question"].strip(),
        "update_window": review["update_window"],
        "regions": [(r, r in review["in_scope_regions"]) for r in regions],
        "outcomes": outcomes,
        "certainties": _certainties(rules),
        "out_of_scope": "\n".join(review["out_of_scope_outcomes"]),
        "intervention_classes": "\n".join(review["intervention_classes_represented"]),
    }


def _int(post, name, current):
    """A box left out of the POST keeps its value; a box with text that is not a whole number is an error."""
    if name not in post:
        return current
    try:
        return int(post[name].strip())
    except ValueError:
        raise ValueError(NUMBER_ERROR) from None


def _text(post, name, current):
    return post.get(name, "").strip() or current


def _lines(post, name, current):
    if name not in post:
        return current
    return [line.strip() for line in post[name].splitlines() if line.strip()]


def _choice(post, name, allowed, current):
    value = post.get(name, current)
    if value not in allowed:
        raise ValueError(f"'{value}' is not one of the choices for {name.replace('_', ' ')}.")
    return value


def from_post(post, review, rules):
    """The review and the rules with the form's values written over them. Raises ValueError with a plain sentence.

    A field left out of the POST keeps its value. Checkboxes are the exception: the browser leaves an
    unticked box out, so they only count when the form's hidden `settings` marker came with them.
    The fields, criteria and overrides arrive as rows and are rebuilt whole when their rows are posted.
    """
    base_rules = rules
    review, rules = copy.deepcopy(review), copy.deepcopy(rules)
    levels = rules["levels"]
    ticked = (lambda name, current: bool(post.get(name))) if post.get("settings") else (lambda name, current: current)

    rules["rubric_version"] = _text(post, "rubric_version", rules["rubric_version"])
    high, moderate, caps = rules["thresholds"]["high"], rules["thresholds"]["moderate"], rules["thresholds"]["a_caps"]
    high["min_total"] = _int(post, "high_min_total", high["min_total"])
    high["min_A"] = _int(post, "high_min_a", high["min_A"])
    moderate["min_total"] = _int(post, "moderate_min_total", moderate["min_total"])
    for a in caps:
        caps[a] = _choice(post, f"a_cap_{a}", levels, caps[a])
    for level in levels:
        rules["suggested_action"][level] = _text(post, f"action_{level}", rules["suggested_action"][level])

    effects = rules["level_steps"]["override_effects"]
    if post.getlist("field_id"):
        rules["fields"] = _fields(post, rules["fields"])
    known = {f["id"]: f for f in rules["fields"]}
    if post.getlist("crit_index"):
        rules["criteria"] = _criteria(post, base_rules["criteria"], known)
    if post.get("settings"):
        rules["overrides"] = _overrides(post, known, effects)

    switches = rules["switches"]
    switches["promote_large_studies_on_moderate"] = ticked("promote_large", switches["promote_large_studies_on_moderate"])
    switches["large_study_n"] = _int(post, "large_study_n", switches["large_study_n"])
    switches["out_of_region_cap"] = _choice(post, "out_of_region_cap", levels + ["none"], switches["out_of_region_cap"])
    switches["out_of_scope_handling"] = _choice(post, "out_of_scope_handling", ["surface", "suppress"], switches["out_of_scope_handling"])
    rules["lmic_income_levels"] = [k for k in rules["income_labels"] if ticked(f"lmic_{k}", k in rules["lmic_income_levels"])]
    rules["regret_top_n"] = _int(post, "regret_top_n", rules["regret_top_n"])

    review["review_id"] = _text(post, "review_id", review["review_id"])
    review["review_question"] = _text(post, "review_question", review["review_question"])
    review["update_window"] = [_int(post, "window_start", review["update_window"][0]), _int(post, "window_end", review["update_window"][1])]
    if post.get("settings"):
        review["in_scope_regions"] = post.getlist("in_scope_regions")
    if post.getlist("outcome_id"):
        review["outcomes"] = _outcomes(post, review["outcomes"], _certainties(rules))
    review["out_of_scope_outcomes"] = _lines(post, "out_of_scope", review["out_of_scope_outcomes"])
    review["intervention_classes_represented"] = _lines(post, "intervention_classes", review["intervention_classes_represented"])
    return review, rules


def _outcomes(post, existing, certainties):
    """One outcome per row of the table. A row with a blank id is dropped; a known id keeps the fields the form does not show."""
    by_id = {o["id"]: o for o in existing}
    rows = zip(*(post.getlist(f"outcome_{field}") for field in OUTCOME_FIELDS))
    outcomes, seen = [], set()
    for id_, name, short, n_studies, certainty, absent, inverted in rows:
        id_ = id_.strip()
        if not id_:
            continue
        if id_ in seen:
            raise ValueError(f"Outcome {id_} is listed twice.")
        if not name.strip():
            raise ValueError(f"Outcome {id_} needs a name.")
        if certainty not in certainties:
            raise ValueError(f"'{certainty}' is not a certainty level the rubric scores.")
        seen.add(id_)
        try:
            n = int(n_studies.strip())
        except ValueError:
            raise ValueError(f"Outcome {id_} needs a whole number of studies.") from None
        outcome = dict(by_id.get(id_, {}), id=id_, name=name.strip(), n_studies=n, certainty=certainty)
        for key, value in (("short", short.strip()), ("absent_contexts", [a.strip() for a in absent.split(",") if a.strip()])):
            if value:
                outcome[key] = value
            else:
                outcome.pop(key, None)
        if inverted == "yes":
            outcome["certainty_inverted"] = True
        else:
            outcome.pop("certainty_inverted", None)
        outcomes.append(outcome)
    if not outcomes:
        raise ValueError("The review needs at least one outcome.")
    return outcomes


def _rows(post, prefix, columns):
    return zip(*(post.getlist(f"{prefix}_{column}") for column in columns))


def _whole(text, what):
    try:
        return int(text.strip())
    except ValueError:
        raise ValueError(f"{what} needs a whole number.") from None


def _ident(text, what):
    text = text.strip()
    if not ID_PATTERN.fullmatch(text):
        raise ValueError(f"{what} '{text}' must start with a letter and use letters, digits, _ or - only.")
    return text


def _typed(field, text):
    """The value as the field's list holds it, so recency_score 1 stays a number; free text stays text."""
    return next((v for v in field.get("values", []) if str(v) == text), text)


def _fields(post, existing):
    """One field per row of the table. A row with a blank id is dropped; a built-in field only takes its label."""
    by_id = {f["id"]: f for f in existing}
    fields, seen = [], set()
    for id_, label, values, prompt, confirmable, type_ in _rows(post, "field", FIELD_COLUMNS):
        if not id_.strip():
            continue
        id_ = _ident(id_, "Field id")
        if id_ in seen:
            raise ValueError(f"Field {id_} is listed twice.")
        seen.add(id_)
        field = dict(by_id.get(id_, {"id": id_, "source": "model"}))
        if field.get("source", "model") != "model":
            field["label"] = label.strip() or field["label"]
            fields.append(field)
            continue
        if not label.strip():
            raise ValueError(f"Field {id_} needs a label.")
        field.update(label=label.strip(), source="model")
        listed = [v.strip() for v in values.split(",") if v.strip()]
        if listed and listed != [str(v) for v in field.get("values", [])]:
            field["values"] = listed
            field.pop("labels", None)
        elif not listed:
            field.pop("values", None)
            field.pop("labels", None)
        for key, value in (("prompt", prompt.strip()), ("confirmable", confirmable == "yes"), ("type", type_ if type_ in FIELD_TYPES else "")):
            if value:
                field[key] = value
            else:
                field.pop(key, None)
        fields.append(field)
    return fields


def _criteria(post, base, known):
    """One criterion per card. Rows over one field give `scores`; rows over several give `parts`, one per field."""
    criteria = {}
    for index, id_, name, help_, max_, default in _rows(post, "crit", CRITERION_COLUMNS):
        if not id_.strip():
            continue
        id_ = _ident(id_, "Criterion id")
        if id_ in criteria:
            raise ValueError(f"Criterion {id_} is listed twice.")
        if not name.strip():
            raise ValueError(f"Criterion {id_} needs a name.")
        scores = {}
        for field, value, points in _rows(post, f"score_{index}", ("field", "value", "points")):
            if not value.strip():
                continue
            if field not in known:
                raise ValueError(f"Criterion {id_} scores a field that is not in the list: {field}.")
            scores.setdefault(field, {})[_typed(known[field], value.strip())] = _whole(points, f"Every points box of criterion {id_}")
        if not scores:
            raise ValueError(f"Criterion {id_} needs at least one scored value.")
        rule = {"name": name.strip(), "help": help_.strip(), "max": _whole(max_, f"The maximum of criterion {id_}")}
        if len(scores) == 1:
            ((field, points),) = scores.items()
            rule.update(source_field=field, default=_whole(default, f"The default of criterion {id_}"), scores=points)
            if known[field].get("labels"):
                rule["value_labels"] = known[field]["labels"]
        else:
            rule["parts"] = [{"source_field": f, "label": known[f]["label"], "scores": s} for f, s in scores.items()]
            rule["default"] = _whole(default, f"The default of criterion {id_}")
        rule.update({k: v for k, v in base.get(id_, {}).items() if k not in ("name", "help", "max") + SCORE_KEYS})
        criteria[id_] = rule
    if not criteria:
        raise ValueError("The rubric needs at least one criterion.")
    return criteria


def _overrides(post, known, effects):
    overrides, seen = [], set()
    for name, label, field, equals, action in _rows(post, "override", OVERRIDE_COLUMNS):
        if not name.strip():
            continue
        name = _ident(name, "Override id")
        if name in seen:
            raise ValueError(f"Override {name} is listed twice.")
        seen.add(name)
        if field not in known:
            raise ValueError(f"Override {name} reads a field that is not in the list: {field}.")
        if not equals.strip():
            raise ValueError(f"Override {name} needs a value to match.")
        if action not in effects:
            raise ValueError(f"'{action}' is not an effect an override can have.")
        overrides.append(
            {
                "name": name,
                "label": label.strip() or name.replace("_", " "),
                "source_field": field,
                "equals": _typed(known[field], equals.strip()),
                "action": action,
            }
        )
    return overrides
