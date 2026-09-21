# Architecture

How Update Signal works, for a developer. The spec in [spec.md](spec.md) holds the
information flow diagram (section 3) and the decision tree (section 4). This file does not
repeat them. It says where each piece lives in the code and why it is there.

## 1. The three stages

A run takes one CSV of records and produces one ranked list.

1. **Stage 1, deterministic.** `signal_tool/tagging.py`. `record_type`, `lane`, countries by
   exact ISO 3166 name match, recency, in-batch duplicates, `secondary_report`,
   `non_english`. No model.
2. **Stage 2, suggested.** `signal_tool/suggest.py`. One model call per record, closed lists
   in and validated JSON out, each value with a verbatim evidence phrase. The geography
   resolver in `geography.py` then unions rule-matched and model-inferred countries.
3. **Stage 3, lookup and score.** `signal_tool/scoring.py`. Certainty lookup from
   `review.yaml`, criteria A–G to a total of 0–15, threshold, region cap, overrides, then the
   reason template.

Stages 1 and 2 run once per upload, for every record including the separate lane, so a
`record_type` override can move a record into scoring without a model call. Stage 3 re-runs
for one record on every confirmation, so it stays pure: tags plus `review.yaml` plus the
rubric in, criteria and level out.

The output is `signals.csv`, a flat file a reviewer sorts in a spreadsheet, plus blank
reviewer columns and the version fields.

## 2. One upload, end to end

1. The upload page (`/new/`) takes the CSV and a saved rubric. `web/views.py` checks the
   header for the three required columns, creates a `Run` with status `processing`, copies
   the rubric's two YAML texts onto the run, and creates one `Record` per row.
2. `start_run` in `web/tasks.py` puts `process_run` on a daemon thread, and the view
   redirects to the run page. The upload page shows a spinner from the click on "Rank the
   records" until the run page opens.
3. `process_run` reads the run's settings with `config(run)`, runs stage 1 over the whole
   batch, and stores one `Tag` row per stage 1 field per record with status `rule`.
4. Stage 2 calls run in a `ThreadPoolExecutor` of `SIGNAL_CONCURRENCY` workers. Only the
   orchestrating thread touches the database; the workers call the model and nothing else.
   As each call returns, `_store` saves the validated response on the `Record`, one `Tag` per
   asked field with status `suggested`, and calls `save_result`, which runs stage 3 and writes
   the `Result`.
5. While the run is `processing`, the run page and a pending record page put `data-poll` on
   `<main>`. The script in `base.html` fetches the page every three seconds and swaps the
   content in place, so the spinners update without a reload. A record with no `Result` yet
   shows a spinner. After a swap, every element with an `id` slides from its old position to
   its new one, so a row is seen moving up the list as it gets ranked.
   `prefers-reduced-motion` turns the slide off.
6. When every call is back the run becomes `done`. An exception anywhere in the thread makes
   it `failed`, with the message in `Run.error`.
7. The reviewer opens a record page and clicks "Agree" or picks a "Change to" value.
   `set_tag` marks the `Tag` row `confirmed` or `overridden`, rebuilds the stage 3 input with
   `entry_for` from the tag rows and the stored model response, and calls `save_result`
   again. No model call. The page redirects back to the record.

## 3. Packages

- `config/` — Django settings, URLs, WSGI. SQLite through the Django ORM, in WAL mode so the
  run page can read while the tagging thread writes. No `admin`, `auth` or `sessions`:
  nobody logs in. `settings.py` loads a git-ignored `.env`; a variable already in the shell
  wins over the file.
- `web/` — the Django app.
  - `models.py` — the five tables, section 4.
  - `tasks.py` — `start_run`, `process_run`, `save_result`, `entry_for`, and `config(run)`,
    which reads the run's stored settings, or the two YAML files when the run has none, plus
    the reference data. Every view and the tagging thread pass the run, so a confirm
    re-scores with the rules the run was tagged with.
  - `views.py` — every page. `GROUP_LABELS` and `TOOL_LABELS` name the columns the tool adds
    itself; every other label comes from the rubric's `fields`.
  - `runconfig.py` — the rubric builder form over the YAML, section 6.
  - `middleware.py` — the password gate, see [hosting.md](hosting.md).
  - `templates/`, `static/app.css`, `tests.py`, `migrations/`.
- `signal_tool/` — the pipeline. **It must never import Django.** It takes and returns plain
  dicts; `web/tasks.py` moves them to and from the tables. One module per stage, tests
  beside them as `test_*.py`:
  - `tagging.py` — stage 1. `geography.py` — the reference loader and the country, region
    and income resolver. `reference.py` — the one-off World Bank download.
  - `suggest.py` — stage 2, `suggest(record, review, rules, client)`. `build_client()`
    returns None without `OPENROUTER_API_KEY`. `compile_prompt(review, rules)` builds the
    system text and the answer schema from the rubric's `fields` with source `model` or
    `review` (`asked_fields`). `validate` coerces every answer onto its field's shape.
    Details in [model.md](model.md).
  - `scoring.py` — stage 3, `score_record(tags, review, rules)`. It returns the criteria and
    the level, and the `criteria_detail` and `level_steps` sentences the pages show.
  - `pipeline.py` — `tags_for(record, model, rules)` turns a tagged record and its model
    response into the tag entry, one tag per asked field. `build_row()` scores one record
    into a `signals.csv` row. `write_csv(rows, handle, rules)` writes the rows.
    `confirmable(rules)` is the ids marked `confirmable`. `columns(rules)` is the CSV header.
  - `evaluate.py` — the D7 checks against a hand sort, section 9.
- `reference/` — `iso3166_regions.csv`, `worldbank_income.json` and `METADATA.json` with
  the download date. Runtime data, section 9.
- `testdata/` — test data only, section 9.

## 4. Tables

`web/models.py`, five tables.

- `Run` — uuid, `status` (`processing`, `done` or `failed`), `error`, `handsort` text,
  `rubric` (the saved `Rubric` the upload page picked), and `rubric_yaml` and `review_yaml`,
  that rubric's two texts copied when the run started, so a later edit of the rubric leaves
  the run alone. Empty means the files on disk, which is what every run made before the
  columns existed used.
- `Record` — the seven `cards.csv` columns, the validated stage 2 `model_response` JSON,
  `model_status`, `model_error`.
- `Tag` — one row per field per record: `value`, `status` (`rule`, `suggested`, `confirmed`
  or `overridden`), `evidence`.
- `Result` — one per record once tagged: `signal_level`, `signal_score`, and `detail`, the
  full `build_row` dict the pages render. A record with no `Result` is still being tagged.
- `Rubric` — uuid, `name`, and the same two YAML texts a `Run` stores. A rubric built in the
  builder. The upload page lists them in a select.

Every run lives in the SQLite file, git-ignored. The run uuid is in the URL. Delete the `Run`
row and its records, tags and results go with it.

## 5. Pages

From `config/urls.py`.

| URL | What it shows |
|---|---|
| `/` | The table of runs, one row per run with its counts. |
| `new/` | The upload form: the CSV and a select of saved rubrics. |
| `run/<uuid>/` | The ranked list: level, score, title, reason and next step, with a text filter. Above it a wrapping row of count blocks, `_counts.html`: records, one block per level with its next step, and set aside. |
| `run/<uuid>/record/<id>/` | One record: how the score was built, how the level was set, and the confirmable tags, each with an "Agree" button and a "Change to" select. |
| `run/<uuid>/record/<id>/tag/` | The POST target of the confirm and override controls. |
| `run/<uuid>/signals.csv` | The download. |
| `run/<uuid>/evaluate/` | The D7 checks against an uploaded hand sort. |
| `run/<uuid>/rubric.yaml`, `run/<uuid>/review.yaml` | The settings the run used. |
| `rubrics/` | The saved rubrics. The first visit stores the two files on disk as the first rubric. |
| `rubrics/new/` | "New rubric": an empty one. |
| `rubrics/<uuid>/` | The builder form, plain sections down one page. |
| `rubrics/<uuid>/copy/` | "Next version": a copy with the last number in its version one higher. |
| `rubrics/<uuid>/prompt/` | The compiled model instructions and the answer schema. |

The counts rise while the run is tagging. The run list at `/` shows the same counts as one
table row per run.

## 6. The rubric builder

`web/runconfig.py` is a form over the two YAML files. `form_context` fills the form from the
files or a `Rubric`. `from_post` writes the form's values over those dicts and raises
`ValueError` with a plain sentence. `dump` stores them as YAML, not JSON: the rubric has
integer keys and `sof_date` is a date. A field left out of the POST keeps its value.

The form edits the thresholds, switches, LMIC groups, next steps, `regret_top_n`, and for
the review the id, question, window, regions, outcomes and the two lists. As rows it edits
the `fields` list, the criteria (id, name, help, max, default and score rows of field,
value, points; rows over one field give `source_field` and `scores`, rows over several give
`parts`) and the overrides (id, label, field, equals, effect). A value is typed by the
field's `values` list, so `recency_score` 1 stays a number. A model field also has an answer
`type`: one value, `list` or `number`. Built-in fields (`source: rules`) only take a label.

Not on the form: record types, duplicates, level names, reason templates, `hand_sheet`,
`allowed_values`. The `FormParser` in `web/tests.py` posts a rendered form back unchanged
and checks the result equals the files.

The builder page uses two pieces of JavaScript: `addRow`, which clones a `<template>` and
gives a new criterion its own index, and the field dialog, a native `<dialog>` that edits one
field row and whose hidden inputs are what the form posts.

## 7. Threads and SQLite

- Tagging runs on a daemon thread inside the web process. There is no queue and no worker
  service. A restart loses an in-flight run. Good enough for one small team on one machine;
  a queue when runs must outlive the process.
- Only the orchestrating thread touches the database. The pool workers call the model and
  nothing else.
- SQLite runs in WAL mode with a 20 second lock timeout, so the polling run page reads while
  the thread writes, and a confirm during tagging waits instead of failing on the lock.
- One Gunicorn worker when hosted, and `runserver --noreload` locally. A second process
  would not see the thread, and the autoreloader kills it on a file save.
- `config/wsgi.py` marks any run still `processing` at boot as `failed` with a plain message,
  because a fresh process has no tagging thread.

## 8. Front end

- Tailwind CSS v4 with DaisyUI v5, built once into `web/static/app.css` with `npm run css`.
  Tailwind reads the class names from `web/templates/`, so rebuild after any template change
  and commit the built file. No CDN, no custom CSS. WhiteNoise serves the file as is, so a
  deploy needs no `collectstatic`.
- JavaScript only where a native control does not do the job: the poll script in
  `base.html`, the theme select there (System, Light or Dark; the choice lives in
  `localStorage` and a one-line script in `<head>` applies it before the first paint), the
  busy spinner on the upload form, the button that adds an outcome row, and the two builder
  scripts in section 6.
- `web/templates/_badge.html` is the one place the level colours live. Include it with
  `level=`; an empty level renders "Not ranked".
- Plain words on screen, raw ids in the CSV. Field labels come from the rubric's `fields`;
  the columns the tool adds itself are named in `GROUP_LABELS` and `TOOL_LABELS` in
  `web/views.py`. Option labels come from `review.yaml` and `rubric.yaml`. The
  per-criterion `help`, `value_labels` and the `level_steps` sentences live in
  `rubric.yaml`; `score_record` returns them as `criteria_detail` and `level_steps`.

## 9. Data contracts

- **`cards.csv`** — columns `record_id`, `title`, `abstract`, `record_type_raw`, `year`,
  `language`, `location`. Only the first three are required; Covidence, Rayyan and
  EPPI-Reviewer supply them. The sample in `testdata/` has 34 records, `SYN-001` to
  `SYN-034`, seeded to trip the equity test: one French record, one 2025 record, one
  retracted article, one protocol, one preprint, one commentary, one conference abstract.
- **`review.yaml`** — the review as data. Nine outcomes `O1`–`O9`, each with `certainty` and
  `n_studies`. `absent_contexts` uses ISO3 codes or UN M49 region labels, so the
  absent-context override matches mechanically. Also `out_of_scope_outcomes`,
  `intervention_classes_represented`, and `allowed_values`, the closed lists the tagger must
  pick from.
- **`rubric.yaml`** — every rule: record types and lanes, `fields` (every field a criterion
  or override can read, with its source, closed list, answer type, model prompt sentence,
  labels, `help` and whether a reviewer confirms it), criteria A–G, thresholds, overrides,
  switches, reason templates, suggested actions, `regret_top_n`. The prompt, the validation,
  the tag entry, the CSV header and the record page all read the `fields` list. Stage 1
  still sets its fields in `tagging.py`, and the scorer and the pages still name the
  built-in fields `outcome_touched`, `sample_size`, `study_design`, `countries_iso3` and
  `lmic_setting`, the ones `rubric_new` keeps in every rubric. The scorer finds the
  certainty criterion by `source_field: outcome_certainty` and runs without it.
- **The hand sort** for the D7 checks, uploaded on the evaluate page, in either shape and
  with commas, semicolons, tabs or pipes. Shape one: one row per record with an id column
  (`record_id` or `Record`) and a level column (`hand_level` or `SIGNAL`; the first word is
  the level, so `HIGH (override)` is High and `ROUTE OUT` is set aside). Shape two: the
  reviewers' scoring sheet (`testdata/handsheet.csv`) with the record ids across the top and
  one question per row. `hand_sheet` in `rubric.yaml` maps each column or question label to
  a tool field and each answer to the tool values it agrees with, with an optional
  plain-words `labels` map; the page shows the meaning of an answer, never the raw letter.
  Other columns of the ranked file (`Total`, `A Rel`…`G CERTAINTY`, `Outcome`,
  `Review certainty`, `Override`) compare against the tool's own columns. Without a level
  column the hand level is the answers scored with the same rubric.
- **`signals.csv`** — `columns(rules)` in `pipeline.py`: the input columns, stage 1, the
  asked fields, the resolved geography and certainty, one column per criterion, then the
  blank reviewer columns and the version fields `model_version`, `prompt_version` and
  `prompt_date`.

### `testdata/`

Test data only. Nothing reads it at run time, and the Docker image leaves it out.

- `cards.csv` — the 34 sample records above. Also the file to upload when you try the tool.
- `handsheet.csv` — the reviewers' scoring sheet for the same 34 records.
- `model/<record_id>-<hash8>.json` — 34 real responses from `anthropic/claude-haiku-4.5`,
  flattened to the compiled shape. `FixtureClient` in `signal_tool/test_suggest.py` serves
  them by the `record_id:` line of the user turn, so no test calls the network. Every upload
  calls the model live.

`web/tests.py` and `signal_tool/test_*.py` both read this folder from the repo root.

### `reference/`

Runtime data, not test data. `signal_tool/geography.py` loads it on every run through
`settings.REFERENCE_DIR`. `iso3166_regions.csv` maps country names to ISO3 codes and UN M49
regions. `worldbank_income.json` maps ISO3 codes to World Bank income groups.
`METADATA.json` holds the sources and the download date. Refresh the World Bank file with
`python -m signal_tool.reference`. The hard rule "never hardcode geography" depends on this
folder.

## 10. Decisions and gaps

- Criterion A is the sum of three yes/no parts, `intervention_tested`, `answers_question`,
  and `lmic_setting == Yes`, one point each. The `Mixed` setting earns 0 in A and 1 in B.
  `relevance` stays a tagged, confirmable field but feeds no score. [spec.md](spec.md)
  section 6 still shows the old mapping.
- LMIC means a World Bank income group in `lmic_income_levels` (`rubric.yaml`), today LIC,
  LMC and UMC, so South Africa counts. The reviewers' sheet marks South Africa as not LMIC.
  The record page shows each country's group and the groups that count, so the team can see
  the rule and change the list.
- `review.yaml` carries `absent_contexts` for O5, O7 and O8 only. The absent-context
  override never fires for the other six outcomes until the team fills the list.
- The open questions in [spec.md](spec.md) section 4 are configuration switches in
  `rubric.yaml`, not code branches: `promote_large_studies_on_moderate`,
  `out_of_region_cap`, `out_of_scope_handling`, `certainty_inverted`.

## 11. History

The first idea lives in [`prototype/`](../prototype/README.md). It is a React and tRPC app
scaffolded on the Manus platform on the first hackathon day. The records, the outcomes and
the scoring rules are TypeScript constants in `server/reviewData.ts` and
`server/reviewEngine.ts`. Nothing could be uploaded, and a rule change was a code change.

The Django tool replaced it the same week. What changed: records come from an uploaded CSV,
the rubric and the review are YAML the team edits without a developer, every model answer
is stored and confirmable, and geography comes from reference data instead of constants.
