import csv
import io
import uuid

import yaml
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render

from signal_tool import evaluate as d7
from signal_tool import pipeline
from signal_tool.geography import load_reference
from signal_tool.suggest import OUTCOME_NONE, build_client
from signal_tool.tagging import load_rules

# SPEC.md section 9: Covidence, Rayyan and EPPI-Reviewer exports all supply these
# three. Everything else in cards.csv is optional.
REQUIRED_COLUMNS = ("record_id", "title", "abstract")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Reviewers, not developers, read these pages. Field ids stay in the CSV.
LABELS = {
    "record_type": ("Record type", "What kind of publication this is."),
    "relevance": ("Relevance", "How closely the record matches the review question."),
    "outcome_touched": ("Outcome", "Which review outcome the record reports on."),
    "harm_reported": ("Harm reported", "Yes moves the record to High."),
    "new_intervention_class": ("New kind of intervention", "Yes moves the record to High."),
}
GROUP_LABELS = {
    "lmic_setting": "Low- or middle-income setting",
    "non_english": "Not in English",
    "study_design": "Study design",
    "sample_size": "Study size",
}
# A rule tag reads as a suggestion too: the reviewer has not looked at it yet.
STATUS_WORDS = {"suggested": "Suggested", "rule": "Suggested", "confirmed": "Agreed", "overridden": "Changed"}


def _read_records(handle):
    rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("The file has a header but no records.")
    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}.")
    return rows


def _config():
    """Read the review, the rubric and the reference data fresh, so an edit shows at once."""
    review = yaml.safe_load(settings.REVIEW_CONFIG.read_text(encoding="utf-8"))
    return review, load_rules(settings.RUBRIC_CONFIG), load_reference(settings.REFERENCE_DIR)


def _run_dir(run_id):
    run_dir = settings.RUNS_DIR / str(run_id)
    if not (run_dir / "tags.json").is_file():
        raise Http404("No such run.")
    return run_dir


def _options(review, rules):
    """The closed list behind each confirm/override control."""
    values = review["allowed_values"]
    return {
        "record_type": list(rules["record_types"]),
        "relevance": values["relevance"],
        "outcome_touched": [o["id"] for o in review["outcomes"]] + [OUTCOME_NONE],
        "harm_reported": values["yes_no_unclear"],
        "new_intervention_class": values["yes_no"],
    }


def _option_labels(review, rules):
    """Plain words for the values a reviewer picks from."""
    labels = {o["id"]: f"{o['id']} {o.get('short') or o['name']}" for o in review["outcomes"]}
    labels[OUTCOME_NONE] = "None of the review outcomes"
    labels.update({k: k.replace("_", " ").capitalize() for k in rules["record_types"]})
    return labels


def upload(request):
    if request.method != "POST":
        return render(request, "upload.html")

    upload_file = request.FILES.get("cards")
    if upload_file is None:
        return render(request, "upload.html", {"error": "Choose a CSV file."}, status=400)

    if upload_file.size > MAX_UPLOAD_BYTES:
        return render(request, "upload.html", {"error": "That file is too large."}, status=400)

    raw = upload_file.read()
    try:
        _read_records(io.StringIO(raw.decode("utf-8-sig")))
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        return render(request, "upload.html", {"error": str(exc)}, status=400)

    run_id = uuid.uuid4()
    run_dir = settings.RUNS_DIR / str(run_id)
    run_dir.mkdir(parents=True)
    (run_dir / "cards.csv").write_bytes(raw)

    review, rules, ref = _config()
    pipeline.run(run_dir, review, rules, ref, settings.MODEL_CACHE, build_client())
    return redirect("run_detail", run_id=run_id)


def run_detail(request, run_id):
    run_dir = _run_dir(run_id)
    review, rules, ref = _config()
    rows = pipeline.build_rows(run_dir, review, rules, ref)
    tagged = pipeline.read_tags(run_dir)
    for row in rows:
        cells = tagged[row["record_id"]]["tags"].values()
        row["changed"] = any(c["status"] in ("confirmed", "overridden") for c in cells)

    # HIGH first, then by score. Unscored (model unavailable) rows sit last but stay listed.
    order = {level: i for i, level in enumerate(reversed(rules["levels"]))}
    signal = sorted(
        (r for r in rows if r["lane"] == "signal"),
        key=lambda r: (order.get(r["signal_level"], len(order)), -(r["signal_score"] or 0), r["record_id"]),
    )
    # SPEC.md section 3: the separate lane is not a signal decision. These records
    # stay visible and never get a score.
    return render(
        request,
        "run_detail.html",
        {
            "run_id": run_id,
            "signal": signal,
            "separate": [r for r in rows if r["lane"] == "separate"],
            "legend": [(level, rules["suggested_action"][level]) for level in reversed(rules["levels"])],
            "low_level": rules["levels"][0],
        },
    )


def record_detail(request, run_id, record_id):
    """One record: its score piece by piece, the level steps, and the tags to check."""
    run_dir = _run_dir(run_id)
    review, rules, ref = _config()
    tagged = pipeline.read_tags(run_dir)
    entry = tagged.get(record_id)
    record = next((r for r in pipeline.read_cards(run_dir) if r["record_id"] == record_id), None)
    if entry is None or record is None:
        raise Http404("No such record.")
    row = pipeline.build_row(record, entry, review, rules, ref)
    tags = entry["tags"]
    options = _options(review, rules)
    option_labels = _option_labels(review, rules)

    checks = [
        {
            "field": field,
            "label": LABELS[field][0],
            "help": LABELS[field][1],
            "value": tags[field]["value"],
            "value_label": option_labels.get(tags[field]["value"], tags[field]["value"]),
            "status_word": STATUS_WORDS[tags[field]["status"]],
            "status": tags[field]["status"],
            "evidence": tags[field]["evidence"],
            "options": [(v, option_labels.get(v, v)) for v in options[field] if v != tags[field]["value"]],
        }
        for field in pipeline.CONFIRMABLE
        if field in tags
    ]

    def fact(label, text, field=None):
        if text in (None, "", []):
            return None
        return {"label": label, "text": text, "evidence": (tags.get(field) or {}).get("evidence", "")}

    design = tags.get("study_design", {}).get("value")
    equity = tags.get("equity_level", {}).get("value")
    factors = tags.get("equity_factors", {}).get("value") or []
    facts = [
        fact("Study design", rules["design_labels"].get(design, design), "study_design"),
        fact("Equity", " · ".join(filter(None, [equity, ", ".join(factors)])), "equity_level"),
        fact("Policy relevance", tags.get("policy_relevance", {}).get("value"), "policy_relevance"),
        fact("Study size", tags.get("sample_size", {}).get("value"), "sample_size"),
        fact("Countries", ", ".join(row["country_names"]), "countries_iso3"),
        fact(GROUP_LABELS["lmic_setting"], row["lmic_setting"]),
    ]
    flags = [
        text
        for flag, text in (
            (row.get("non_english"), "Not in English"),
            (row.get("secondary_report"), "Secondary report of a study already in the batch"),
            (row.get("is_duplicate"), f"Duplicate of {row.get('duplicate_of')}"),
            (row.get("out_of_region"), "No country in the review's regions"),
            (row.get("validation_errors"), "The model gave values off the list, replaced with safe defaults: "
             + "; ".join(row.get("validation_errors") or [])),
        )
        if flag
    ]
    return render(
        request,
        "record_detail.html",
        {
            "run_id": run_id,
            "row": row,
            "checks": checks,
            "facts": [f for f in facts if f],
            "flags": flags,
            "unavailable": entry["model"]["model_status"] != "ok",
        },
    )


def set_tag(request, run_id, record_id):
    """Confirm or override one of the five human-checked tags, then re-run stage 3 only."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")
    run_dir = _run_dir(run_id)
    review, rules, ref = _config()
    tagged = pipeline.read_tags(run_dir)
    field, value = request.POST.get("field"), request.POST.get("value")
    entry = tagged.get(record_id)
    if entry is None or field not in pipeline.CONFIRMABLE or field not in entry["tags"]:
        return HttpResponseBadRequest("Unknown record or field.")
    if value not in _options(review, rules)[field]:
        return HttpResponseBadRequest("Value is not on the closed list.")

    cell = entry["tags"][field]
    cell["status"] = "confirmed" if value == cell["value"] else "overridden"
    cell["value"] = value
    pipeline.write_tags(run_dir, tagged)
    pipeline.rescore(run_dir, review, rules, ref)
    return redirect("record_detail", run_id=run_id, record_id=record_id)


def signals_csv(request, run_id):
    run_dir = _run_dir(run_id)
    return FileResponse((run_dir / "signals.csv").open("rb"), as_attachment=True, filename="signals.csv")


def evaluate(request, run_id):
    run_dir = _run_dir(run_id)
    handsort_path = run_dir / "handsort.csv"
    error = None
    if request.method == "POST":
        upload_file = request.FILES.get("handsort")
        if upload_file is None:
            error = "Choose a CSV file."
        else:
            try:
                text = upload_file.read().decode("utf-8-sig")
                d7.parse_handsort(text)
            except (UnicodeDecodeError, csv.Error, ValueError) as exc:
                error = str(exc)
            else:
                handsort_path.write_text(text, encoding="utf-8")
                return redirect("evaluate", run_id=run_id)

    review, rules, ref = _config()
    rows = pipeline.build_rows(run_dir, review, rules, ref)
    equity = [(GROUP_LABELS.get(k, k), groups) for k, groups in d7.equity(rows, rules).items()]
    context = {"run_id": run_id, "error": error, "equity": equity, "top_n": rules["regret_top_n"]}
    if handsort_path.is_file():
        handsort = d7.parse_handsort(handsort_path.read_text(encoding="utf-8"))
        context["agreement"] = d7.agreement(rows, handsort, rules)
        option_labels = _option_labels(review, rules)
        for record in context["agreement"]["records"]:
            record["tags"] = [option_labels.get(record[f], record[f]) for f in pipeline.CONFIRMABLE]
        context["regret"] = d7.regret(rows, handsort, rules["regret_top_n"])
        context["labels"] = [LABELS[f][0] for f in pipeline.CONFIRMABLE]
    return render(request, "evaluate.html", context, status=400 if error else 200)
