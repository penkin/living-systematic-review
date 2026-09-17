import csv
import io
import uuid

from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render

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

    return redirect("run_detail", run_id=run_id)


def run_detail(request, run_id):
    run_dir = settings.RUNS_DIR / str(run_id)
    cards = run_dir / "cards.csv"
    if not cards.is_file():
        raise Http404("No such run.")

    with cards.open(encoding="utf-8-sig", newline="") as handle:
        records = _read_records(handle)

    return render(request, "run_detail.html", {"run_id": run_id, "records": records})
