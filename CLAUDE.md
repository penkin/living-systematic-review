# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
.venv/bin/python manage.py migrate      # create or update db.sqlite3, once per checkout and after a model change
.venv/bin/python manage.py runserver --noreload   # serve the tool at http://127.0.0.1:8000/
.venv/bin/python manage.py test         # run every test, web and signal_tool
.venv/bin/python manage.py test web.tests.UploadTests.test_header_only_is_rejected
.venv/bin/python -m signal_tool.reference   # refresh reference/worldbank_income.json and METADATA.json
uv pip install --python .venv/bin/python -r requirements.txt
npm install && npm run css                  # rebuild web/static/app.css after a template change
```

Set `OPENROUTER_API_KEY` so stage 2 can call the model. Without it the upload page
refuses the file. A model call that fails leaves the record listed but unscored.
`SIGNAL_MODEL` picks the model, default `anthropic/claude-haiku-4.5`. `SIGNAL_CONCURRENCY`
sets how many model calls run side by side, default 8. `OPENROUTER_BASE_URL`
picks the endpoint, default `https://openrouter.ai/api/v1`; any OpenAI-compatible chat
endpoint works. Stage 2 calls it with the stdlib `urllib`, so no provider SDK is installed.
Put the variables in a git-ignored `.env` at the repo root (copy `.env.example`);
`config/settings.py` loads it, and a variable already in the shell wins over the file.

Recreate the environment with `uv venv --python 3.13 .venv`. Django 6 needs Python
3.12 or newer; the system `python3` is 3.9 and will not do.

Run the server with `--noreload`. Tagging runs in a thread inside the server process,
and the autoreloader restarts that process on a file save, which leaves the run stuck
in `processing`. Set `SIGNAL_DB` to put the SQLite file somewhere other than
`db.sqlite3` at the repo root.

## What the tool is

A living systematic review gets new records. The tool tags each record, looks up how
certain the review already is about the outcome the record touches, and ranks it
High / Moderate / Low with a reason of fifteen words or fewer. The reviewer decides.
The tool suggests.

## Layout

- `config/` — Django settings, URLs, WSGI. SQLite through the Django ORM, in WAL mode
  so the run page can read while the tagging thread writes. No `admin`, `auth` or
  `sessions`: nobody logs in.
- `web/` — `models.py`, `tasks.py`, `views.py`, the templates, `static/app.css`,
  `tests.py`, `migrations/`.
  Pages: `/` upload, `run/<uuid>/` the ranked list, `run/<uuid>/record/<id>/` one
  record with its score breakdown and the confirm/override controls,
  `run/<uuid>/signals.csv` the download, `run/<uuid>/evaluate/` the D7 checks.
  - `models.py` — four tables. `Run` (uuid, status `processing`, `done` or `failed`,
    `error`, `handsort` text). `Record` (the seven `cards.csv` columns, the validated
    stage 2 `model_response` JSON, `model_status`, `model_error`). `Tag` (one row per
    field per record: `value`, `status` `rule`, `suggested`, `confirmed` or
    `overridden`, `evidence`). `Result` (one per record once tagged: `signal_level`,
    `signal_score`, and `detail`, the full `build_row` dict the pages render).
    A record with no `Result` is still being tagged.
  - `tasks.py` — `start_run` puts `process_run` on a daemon thread. Stage 1 over the
    whole batch, then stage 2 calls in a `ThreadPoolExecutor`; only the orchestrating
    thread touches the database. `save_result` runs stage 3 for one record and is
    what a confirm calls. `config()` reads the two yaml files and the reference data.
- `signal_tool/` — the pipeline. **It must never import Django.** It takes and returns
  plain dicts; `web/tasks.py` moves them to and from the tables. One module per
  stage, tests beside them as `test_*.py`:
  - `tagging.py` — stage 1. `geography.py` — reference loader and the country, region
    and income resolver. `reference.py` — the one-off World Bank download.
  - `suggest.py` — stage 2, `suggest(record, review, client)`: the model call and the
    closed-list validation. `build_client()` returns None without `OPENROUTER_API_KEY`.
  - `scoring.py` — stage 3, `score_record(tags, review, rules)`.
  - `pipeline.py` — `tags_for()` turns a tagged record and its model response into
    the tag entry, `build_row()` scores one record into a `signals.csv` row,
    `write_csv()` writes the rows. `evaluate.py` — the D7 checks.
  - `testdata/model/<record_id>-<hash8>.json` — 34 real model responses for
    `cards.csv`, used as test fixtures. `FixtureClient` in `test_suggest.py` serves
    them by `record_id`.
- `rubric.yaml` — every rule: record types and lanes, criteria A–G, thresholds,
  overrides, switches, reason templates, suggested actions, `regret_top_n`.
- `review.yaml` — the review as data: outcomes with certainty, closed lists, regions.
- `reference/` — `iso3166_regions.csv`, `worldbank_income.json`, and `METADATA.json`
  with the download date.
- `db.sqlite3` — every run, git-ignored. The run uuid is in the URL. Delete the `Run`
  row and its records, tags and results go with it.

## Hard rules

- Never include or exclude a study. Never decide that the review needs an update.
- Every model output is `suggested` until a human confirms it. Five fields carry a
  confirm/override control: `record_type`, `relevance`, `outcome_touched`,
  `harm_reported`, `new_intervention_class`.
- Low records stay visible. Deprioritise them, never hide them.
- Never infer outcome certainty. Look it up in `review.yaml`.
- Never hardcode geography. Countries, regions, and income groups come from
  `reference/` and from the World Bank API.
- Never repeat the stage 2 model call because a human changed a tag. The validated
  response is stored in `Record.model_response`; a confirm re-runs stage 3 from it.
- Never write the rubric, the thresholds, the overrides, or the lane rules into code.
  They live in `rubric.yaml`. The review team edits them without a developer present.
- Never drop a record. A separate-lane type leaves the scoring, not the output.
  `SPEC.md:37` calls the separate lane "NOT a signal decision".
- The open questions in `SPEC.md` section 4 are configuration switches, not code
  branches: `promote_large_studies_on_moderate`, `out_of_region_cap`,
  `out_of_scope_handling`, `certainty_inverted`.

## Pipeline

1. **Stage 1, deterministic.** `record_type`, `lane`, countries by exact ISO 3166
   name match, recency, in-batch duplicates, `secondary_report`, `non_english`.
2. **Stage 2, suggested.** One model call per record, closed lists in and
   validated JSON out, each value with a verbatim evidence phrase. The geography
   resolver then unions rule-matched and model-inferred countries.
3. **Stage 3, lookup and score.** Certainty lookup from `review.yaml`, criteria A–G
   to a total of 0–15, threshold, region cap, overrides, then the reason template.
4. **Output.** `signals.csv`, a flat file a reviewer sorts in a spreadsheet, plus
   blank reviewer columns and the version fields.

Stages 1 and 2 run once per upload, for every record including the separate lane, so
a `record_type` override can move a record into scoring without a model call. Stage 3
re-runs for the one record on every confirmation, so keep it pure: tags plus
`review.yaml` plus the rubric in, criteria and level out.

The upload page submits as soon as the reviewer picks a file and shows a spinner until
the run page opens. While the run is `processing`, the run page and a pending record
page put `data-poll` on `<main>`. The script in `base.html` then fetches the page every
three seconds and swaps the content in place, so the spinners update without a reload.
Each record with no `Result` yet shows a spinner. After a swap, every element with an
`id` slides from its old position to its new one, so a row is seen moving up the list
as it gets ranked. `prefers-reduced-motion` turns the slide off.

Read `SPEC.md` section 4 before you change the decision tree. Read section 6 before
you change the rubric. Read section 5 to find which stage produces a field.

## Web pages

Reviewers, not developers, read the pages. Keep them simple.

- The style is Tailwind CSS v4 with DaisyUI v5, built once into `web/static/app.css`
  with `npm run css` (`npm install` first; `node_modules/` is git-ignored). Tailwind
  reads the class names from `web/templates/`, so rebuild the CSS after any template
  change and commit the built file. No CDN, no custom CSS. JavaScript is fine where a
  native control does not do the job. Today that is the poll script in `base.html` and
  the two event attributes on the upload form.
- `web/templates/_badge.html` is the one place the level colours live. Include it
  with `level=`; an empty level renders "Not ranked".
- Plain words on screen, raw ids in the CSV. Field labels live in `LABELS` in
  `web/views.py`. Option labels come from `review.yaml` and `rubric.yaml`. The
  per-criterion `help`, `value_labels` and the `level_steps` sentences live in
  `rubric.yaml`; `score_record` returns them as `criteria_detail` and `level_steps`.
- The list at `run/<uuid>/` shows level, score, title, reason and next step. Above it
  sits a wrapping row of count blocks: records, one block per level with its next step,
  and set aside. The counts rise while the run is tagging. The
  record page at `run/<uuid>/record/<record_id>/` shows how the score was built,
  how the level was set, and the five tags with an "Agree" button and a "Change to"
  select. A tag change redirects back to the record page.

## Data contracts

- `cards.csv` — 34 records, `SYN-001` to `SYN-034`. Columns: `record_id`, `title`,
  `abstract`, `record_type_raw`, `year`, `language`, `location`. Only the first three
  are required for a future import; Covidence, Rayyan, and EPPI-Reviewer supply them.
  The set is seeded to trip the equity test: one French record, one 2025 record, one
  retracted article, one protocol, one preprint, one commentary, one conference
  abstract.
- `review.yaml` — nine outcomes `O1`–`O9`, each with `certainty` and `n_studies`.
  `absent_contexts` uses ISO3 codes or UN M49 region labels, so the absent-context
  override matches mechanically. The file also holds `out_of_scope_outcomes`,
  `intervention_classes_represented`, and `allowed_values`, the closed lists the
  tagger must pick from.
- `handsort.csv` — the reviewer's own sort for the D7 checks. Columns `record_id`
  and `hand_level` with `HIGH`, `MODERATE` or `LOW`.

## Decisions and gaps

- Criterion A is the sum of three yes/no parts, `intervention_tested`,
  `answers_question`, and `lmic_setting == Yes`, one point each. The `Mixed` setting
  earns 0 in A and 1 in B. `relevance` stays a tagged, confirmable field but feeds no
  score. `SPEC.md:177` still shows the old mapping.
- `review.yaml` carries `absent_contexts` for O5, O7 and O8 only. The absent-context
  override never fires for the other six outcomes until the team fills the list.
- `signal_tool/testdata/model/` holds real responses from `anthropic/claude-haiku-4.5`.
  They only serve the tests. Every upload calls the model live.
