"""Tag and score one upload in a background thread.

Only this thread touches the database. The worker threads call the model and nothing else.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
from django.conf import settings
from django.db import connection, transaction

from signal_tool import pipeline
from signal_tool.geography import load_reference
from signal_tool.suggest import suggest
from signal_tool.tagging import load_rules, tag
from web.models import Result, Run, Tag


def config(run=None):
    """The review, the rules and the reference data for one run or rubric. A run without stored settings uses the files on disk."""
    review = yaml.safe_load(run.review_yaml) if run and run.review_yaml else load_rules(settings.REVIEW_CONFIG)
    rules = yaml.safe_load(run.rubric_yaml) if run and run.rubric_yaml else load_rules(settings.RUBRIC_CONFIG)
    return review, rules, load_reference(settings.REFERENCE_DIR)


def start_run(run_id, client):
    # ponytail: a thread in the web process; a restart loses an in-flight run. A queue when runs outlive the process.
    threading.Thread(target=process_run, args=(run_id, client), daemon=True).start()


def process_run(run_id, client):
    run = Run.objects.get(pk=run_id)
    try:
        review, rules, ref = config(run)
        records = list(run.records.all())
        cards = tag([record.as_dict() for record in records], rules, review, ref)
        Tag.objects.bulk_create(
            Tag(record=record, field=field, value=card.get(field), status="rule")
            for record, card in zip(records, cards)
            for field in pipeline.STAGE_ONE
        )
        workers = int(os.environ.get("SIGNAL_CONCURRENCY", "8"))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(suggest, card, review, rules, client): (record, card) for record, card in zip(records, cards)}
            for future in as_completed(futures):
                record, card = futures[future]
                _store(record, card, future.exception(), future, review, rules, ref)
        run.status = Run.DONE
    except Exception as exc:
        run.status, run.error = Run.FAILED, f"{type(exc).__name__}: {exc}"
    finally:
        run.save(update_fields=["status", "error"])
        connection.close()


def _store(record, card, exc, future, review, rules, ref):
    model = None if exc else future.result()
    with transaction.atomic():
        record.model_response = model
        record.model_status = "unavailable" if exc else "ok"
        record.model_error = f"{type(exc).__name__}: {exc}" if exc else ""
        record.save(update_fields=["model_response", "model_status", "model_error"])
        entry = pipeline.tags_for(card, model, rules)
        Tag.objects.bulk_create(
            Tag(record=record, field=field, **cell)
            for field, cell in entry["tags"].items()
            if field not in pipeline.STAGE_ONE
        )
        save_result(record, entry, review, rules, ref)


def entry_for(record):
    """The stage 3 input for one record, rebuilt from its Tag rows and stored model response."""
    tags = {t.field: {"value": t.value, "status": t.status, "evidence": t.evidence} for t in record.tags.all()}
    return {"tags": tags, "model": pipeline.model_meta(record.model_response)}


def save_result(record, entry, review, rules, ref):
    row = pipeline.build_row(record.as_dict(), entry, review, rules, ref)
    Result.objects.update_or_create(
        record=record,
        defaults={"signal_level": row["signal_level"], "signal_score": row["signal_score"] or None, "detail": row},
    )
    return row
