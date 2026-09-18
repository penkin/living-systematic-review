import collections
import csv
import io

from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from signal_tool import evaluate as d7
from signal_tool import pipeline
from signal_tool.suggest import OUTCOME_NONE, build_client
from web.models import Record, Run, Tag
from web.tasks import config, entry_for, save_result, start_run

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
    repeated = sorted(k for k, n in collections.Counter(r["record_id"] for r in rows).items() if n > 1)
    if repeated:
        raise ValueError(f"Repeated record_id: {', '.join(repeated)}.")
    return rows


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


def _rows(run):
    """One display row per record. A record without a Result is still being tagged."""
    rows = []
    for record in run.records.select_related("result").prefetch_related("tags"):
        result = getattr(record, "result", None)
        if result is None:
            row = {**record.as_dict(), "signal_level": "", "signal_score": None, "lane": "signal", "pending": True}
            row.update({t.field: t.value for t in record.tags.all()})
        else:
            row = dict(result.detail)
        row["changed"] = any(t.status in ("confirmed", "overridden") for t in record.tags.all())
        rows.append(row)
    return rows


def upload(request):
    if request.method != "POST":
        return render(request, "upload.html")

    upload_file = request.FILES.get("cards")
    if upload_file is None:
        return render(request, "upload.html", {"error": "Choose a CSV file."}, status=400)

    if upload_file.size > MAX_UPLOAD_BYTES:
        return render(request, "upload.html", {"error": "That file is too large."}, status=400)

    try:
        rows = _read_records(io.StringIO(upload_file.read().decode("utf-8-sig")))
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        return render(request, "upload.html", {"error": str(exc)}, status=400)

    client = build_client()
    if client is None:
        error = "Set OPENROUTER_API_KEY in .env to tag records, then restart the server."
        return render(request, "upload.html", {"error": error}, status=400)

    with transaction.atomic():
        run = Run.objects.create(filename=upload_file.name)
        Record.objects.bulk_create(
            Record(run=run, **{f: (row.get(f) or "").strip() for f in Record.INPUT_FIELDS}) for row in rows
        )
    start_run(run.pk, client)
    return redirect("run_detail", run_id=run.pk)


def run_detail(request, run_id):
    run = get_object_or_404(Run, pk=run_id)
    review, rules, ref = config()
    rows = _rows(run)

    # HIGH first, then by score. Unscored rows sit last but stay listed; rows still being tagged sit below them.
    order = {level: i for i, level in enumerate(reversed(rules["levels"]))}
    signal = sorted(
        (r for r in rows if r["lane"] == "signal"),
        key=lambda r: (r.get("pending", False), order.get(r["signal_level"], len(order)), -(r["signal_score"] or 0), r["record_id"]),
    )
    # SPEC.md section 3: the separate lane is not a signal decision. These records
    # stay visible and never get a score.
    uncertainty = rules["criteria"]["G"]
    return render(
        request,
        "run_detail.html",
        {
            "run_id": run_id,
            "run": run,
            "total": len(rows),
            "tagged": sum(1 for r in rows if not r.get("pending")),
            "signal": signal,
            "separate": [r for r in rows if r["lane"] == "separate"],
            "legend": [(level, rules["suggested_action"][level]) for level in reversed(rules["levels"])],
            "low_level": rules["levels"][0],
            "outcomes": [dict(o, points=uncertainty["scores"].get(o["certainty"], uncertainty["default"])) for o in review["outcomes"]],
            "uncertainty_max": uncertainty["max"],
            "sof_date": review.get("sof_date"),
            "out_of_scope": review["out_of_scope_outcomes"],
        },
    )


def record_detail(request, run_id, record_id):
    """One record: its score piece by piece, the level steps, and the tags to check."""
    record = get_object_or_404(Record.objects.select_related("result"), run_id=run_id, record_id=record_id)
    review, rules, ref = config()
    tags = entry_for(record)["tags"]
    result = getattr(record, "result", None)
    if result is None:
        row = {**record.as_dict(), "lane": tags.get("lane", {}).get("value", "signal"), "country_names": []}
    else:
        row = result.detail
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
        fact(GROUP_LABELS["lmic_setting"], row.get("lmic_setting")),
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
            "pending": result is None,
            "unavailable": result is not None and record.model_status != "ok",
            "model_error": record.model_error,
        },
    )


def set_tag(request, run_id, record_id):
    """Confirm or override one of the five human-checked tags, then re-run stage 3 for this record only."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only.")
    get_object_or_404(Run, pk=run_id)
    review, rules, ref = config()
    field, value = request.POST.get("field"), request.POST.get("value")
    cell = Tag.objects.filter(record__run_id=run_id, record__record_id=record_id, field=field).select_related("record").first()
    if cell is None or field not in pipeline.CONFIRMABLE:
        return HttpResponseBadRequest("Unknown record or field.")
    if value not in _options(review, rules)[field]:
        return HttpResponseBadRequest("Value is not on the closed list.")

    cell.status = "confirmed" if value == cell.value else "overridden"
    cell.value = value
    cell.save(update_fields=["status", "value"])
    save_result(cell.record, entry_for(cell.record), review, rules, ref)
    # Land on the row the reviewer just checked, not at the top of the page.
    return redirect(reverse("record_detail", args=[run_id, record_id]) + f"#tag-{field}")


def signals_csv(request, run_id):
    run = get_object_or_404(Run, pk=run_id)
    handle = io.StringIO()
    pipeline.write_csv(_rows(run), handle)
    return HttpResponse(
        handle.getvalue(),
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="signals.csv"'},
    )


def evaluate(request, run_id):
    run = get_object_or_404(Run, pk=run_id)
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
                run.handsort = text
                run.save(update_fields=["handsort"])
                return redirect("evaluate", run_id=run_id)

    review, rules, ref = config()
    rows = [r for r in _rows(run) if not r.get("pending")]
    equity = [(GROUP_LABELS.get(k, k), groups) for k, groups in d7.equity(rows, rules).items()]
    context = {"run_id": run_id, "error": error, "equity": equity, "top_n": rules["regret_top_n"]}
    if run.handsort:
        handsort = d7.parse_handsort(run.handsort)
        context["agreement"] = d7.agreement(rows, handsort, rules)
        option_labels = _option_labels(review, rules)
        for record in context["agreement"]["records"]:
            record["tags"] = [option_labels.get(record[f], record[f]) for f in pipeline.CONFIRMABLE]
        context["regret"] = d7.regret(rows, handsort, rules["regret_top_n"])
        context["labels"] = [LABELS[f][0] for f in pipeline.CONFIRMABLE]
    return render(request, "evaluate.html", context, status=400 if error else 200)
