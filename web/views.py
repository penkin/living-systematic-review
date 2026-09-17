import csv
import io
import uuid

import yaml
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse

from signal_tool import evaluate as d7
from signal_tool import pipeline
from signal_tool.geography import load_reference
from signal_tool.suggest import OUTCOME_NONE, build_client
from signal_tool.tagging import load_rules

# SPEC.md section 9: Covidence, Rayyan and EPPI-Reviewer exports all supply these
# three. Everything else in cards.csv is optional.
REQUIRED_COLUMNS = ("record_id", "title", "abstract")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


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
    options = _options(review, rules)

    for row in rows:
        entry = tagged[row["record_id"]]
        row["controls"] = [
            {"field": field, "options": options[field], **entry["tags"][field]}
            for field in pipeline.CONFIRMABLE
            if field in entry["tags"]
        ]
        row["evidence"] = [
            (field, cell["evidence"]) for field, cell in entry["tags"].items() if cell.get("evidence")
        ]
        row["criteria"] = [(c, row[c]) for c in "ABCDEFG"] if row["signal_level"] else []

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
            "low_level": rules["levels"][0],
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
    return redirect(reverse("run_detail", kwargs={"run_id": run_id}) + f"#{record_id}")


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
    context = {"run_id": run_id, "error": error, "equity": d7.equity(rows, rules), "top_n": rules["regret_top_n"]}
    if handsort_path.is_file():
        handsort = d7.parse_handsort(handsort_path.read_text(encoding="utf-8"))
        context["agreement"] = d7.agreement(rows, handsort, rules)
        context["regret"] = d7.regret(rows, handsort, rules["regret_top_n"])
    return render(request, "evaluate.html", context, status=400 if error else 200)
