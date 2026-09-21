# AGENTS.md

Instructions for any coding agent that works in this repository. Claude Code reads this file
through `CLAUDE.md`. Codex, Cursor, Gemini CLI and Copilot read it directly.

## What the tool is

A living systematic review gets new records. The tool tags each record, looks up how
certain the review already is about the outcome the record touches, and ranks it
High / Moderate / Low with a reason of fifteen words or fewer. The reviewer decides.
The tool suggests.

## Commands

```bash
.venv/bin/python manage.py migrate      # create or update db.sqlite3, once per checkout and after a model change
.venv/bin/python manage.py runserver --noreload   # serve the tool at http://127.0.0.1:8000/
.venv/bin/python manage.py test         # run every test, web and signal_tool
.venv/bin/python manage.py test web.tests.UploadTests.test_header_only_is_rejected
.venv/bin/python -m signal_tool.reference   # refresh reference/worldbank_income.json and METADATA.json
uv pip install --python .venv/bin/python -r requirements.txt
npm install && npm run css                  # rebuild web/static/app.css after a template change
fly deploy --ha=false                       # one way to host it; docs/hosting.md has the others
```

Set `OPENROUTER_API_KEY` so stage 2 can call the model. Without it the upload page
refuses the file. A model call that fails leaves the record listed but unscored.
`SIGNAL_MODEL` picks the model, default `anthropic/claude-haiku-4.5`. `SIGNAL_CONCURRENCY`
sets how many model calls run side by side, default 8. `OPENROUTER_BASE_URL` picks the
endpoint, default `https://openrouter.ai/api/v1`; any OpenAI-compatible chat endpoint works,
see `docs/model.md`. Stage 2 calls it with the stdlib `urllib`, so no provider SDK is
installed. Put the variables in a git-ignored `.env` at the repo root (copy `.env.example`);
`config/settings.py` loads it, and a variable already in the shell wins over the file.

Recreate the environment with `uv venv --python 3.13 .venv`. Django 6 needs Python 3.12 or
newer; the system `python3` is 3.9 and will not do.

Run the server with `--noreload`. Tagging runs in a thread inside the server process, and
the autoreloader restarts that process on a file save, which leaves the run stuck in
`processing`. Set `SIGNAL_DB` to put the SQLite file somewhere other than `db.sqlite3` at
the repo root.

Hosting is a guide, not a fixed deployment: `docs/hosting.md`. The repo ships a `Dockerfile`
and a `fly.toml` as starting points. Deploy only when no run is `processing`; a restart
marks a run in progress as failed.

## Layout

- `config/` — Django settings, URLs, WSGI. SQLite in WAL mode. No `admin`, `auth` or `sessions`.
- `web/` — `models.py`, `tasks.py` (the tagging thread), `views.py`, `runconfig.py` (the
  rubric builder form), `middleware.py` (the password gate), templates, `static/app.css`,
  `tests.py`, `migrations/`.
- `signal_tool/` — the pipeline, one module per stage, tests beside them as `test_*.py`.
  **It must never import Django.** Plain dicts in and out; `web/tasks.py` moves them to and
  from the tables.
- `rubric.yaml`, `review.yaml` — every rule, and the review as data. The review team edits them.
- `reference/` — the geography and income data the pipeline reads at run time. Not test data.
- `testdata/` — `cards.csv`, `handsheet.csv` and the 34 stored model responses. Tests only.
- `docs/` — the spec and the guides. `prototype/` — the first static prototype, not part of the tool.

`docs/architecture.md` has the tables, the pages, the threads and the data contracts.

## Hard rules

- Never include or exclude a study. Never decide that the review needs an update.
- Every model output is `suggested` until a human confirms it. Every field marked
  `confirmable` in the rubric carries a confirm/override control; today `record_type`,
  `relevance`, `outcome_touched`, `harm_reported`, `new_intervention_class`.
- Low records stay visible. Deprioritise them, never hide them.
- Never infer outcome certainty. Look it up in `review.yaml`.
- Never hardcode geography. Countries, regions, and income groups come from `reference/`
  and from the World Bank API.
- Never repeat the stage 2 model call because a human changed a tag. The validated response
  is stored in `Record.model_response`; a confirm re-runs stage 3 from it.
- Never write the rubric, the thresholds, the overrides, or the lane rules into code. They
  live in `rubric.yaml`. The review team edits them without a developer present.
- Never drop a record. A separate-lane type leaves the scoring, not the output. The diagram
  in `docs/spec.md` section 3 calls the separate lane "NOT a signal decision".
- The open questions in `docs/spec.md` section 4 are configuration switches, not code
  branches: `promote_large_studies_on_moderate`, `out_of_region_cap`,
  `out_of_scope_handling`, `certainty_inverted`.

## Working rules

- Keep stage 3 pure: tags plus `review.yaml` plus the rubric in, criteria and level out. It
  re-runs for one record on every confirmation.
- Stages 1 and 2 run once per upload, for every record, the separate lane included.
- Rebuild `web/static/app.css` with `npm run css` after any template change and commit the
  built file. Tailwind reads the class names from `web/templates/`. No CDN, no custom CSS.
- Reviewers, not developers, read the pages. Keep them simple. Plain words on screen, raw
  ids in the CSV. Field labels come from the rubric's `fields`; the labels of the columns the
  tool adds itself live in `GROUP_LABELS` and `TOOL_LABELS` in `web/views.py`. Option labels,
  `help` and the `level_steps` sentences live in the two YAML files.
- JavaScript only where a native control does not do the job.
- Tests sit beside the code: `web/tests.py` and `signal_tool/test_*.py`. Both read
  `testdata/`. The stored model responses there mean a test never calls the network.
- Read `docs/spec.md` section 4 before you change the decision tree, section 6 before you
  change the rubric, section 5 to find which stage produces a field.

## Docs

- `README.md` — quick start, configuration, layout.
- `docs/architecture.md` — how it all works.
- `docs/hosting.md` — how to host it.
- `docs/model.md` — the stage 2 model call and the provider options.
- `docs/spec.md` — the spec: information flow, decision tree, field dictionary, rubric v0.
- `prototype/README.md` — the first prototype.
- `AUTHORS.md` — who built it.
