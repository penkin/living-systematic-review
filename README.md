# Update Signal

A living systematic review gets new records. Update Signal tags each record, looks up how
certain the review already is about the outcome the record touches, and ranks it High,
Moderate or Low with a reason of fifteen words or fewer. The reviewer decides. The tool
suggests.

## What it never does

- Include or exclude a study, or decide that the review needs an update.
- Assert a model tag. Every model output is a suggestion until a human confirms it.
- Hide Low records. They stay visible, lower down the list.
- Infer outcome certainty. It is looked up from the review's own Summary of Findings.
- Hardcode geography. Countries, regions and income groups come from reference data.

[docs/spec.md](docs/spec.md) section 2 is the full list.

## Quick start

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). The `python3` that
ships with macOS is 3.9 and will not do.

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

Open `.env` and set `OPENROUTER_API_KEY`. Without a key the upload page refuses the file.

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver --noreload
```

Open http://127.0.0.1:8000/new/ and upload [testdata/cards.csv](testdata/cards.csv). Each
record calls the model once, and the list fills in as the answers come back.

Keep `--noreload`. Tagging runs in a thread inside the server process, and the autoreloader
would restart that process on a file save and lose the run.

The pages are styled with Tailwind CSS and DaisyUI, built once into `web/static/app.css`.
Rebuild it only after a template change:

```bash
npm install && npm run css
```

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `OPENROUTER_API_KEY` | none | The key for the model endpoint. Required to rank anything. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible chat endpoint. |
| `SIGNAL_MODEL` | `anthropic/claude-haiku-4.5` | The model that tags the records. |
| `SIGNAL_CONCURRENCY` | `8` | How many model calls run side by side. |
| `SIGNAL_DB` | `db.sqlite3` at the repo root | Where the SQLite file lives. |
| `APP_PASSWORD` | empty, gate off | One shared password the browser asks for. |
| `DJANGO_SECRET_KEY` | a development-only value | Set a long random value when hosted. |
| `DJANGO_DEBUG` | `0` | Set `1` on your own machine to see the error pages. |
| `DJANGO_ALLOWED_HOSTS` | localhost only | Comma-separated host names when hosted. |

Put the variables in the git-ignored `.env` at the repo root. A variable already in the shell
wins over the file.

## The rubric and the review

`rubric.yaml` holds every rule: the fields the model is asked for, the criteria, the
thresholds, the overrides and the reason templates. `review.yaml` holds the review as data:
the outcomes with their certainty, the closed lists and the regions. The review team edits
both without a developer, either in the files or in the rubric builder at `/rubrics/`. Each
run keeps a copy of the rubric it was ranked with, so a later edit leaves old runs alone.

## Tests

```bash
.venv/bin/python manage.py test
```

Tests read `testdata/` and never call the network. The model answers for the 34 sample
records are stored there.

## Hosting

The tool needs one instance, a disk for the SQLite file, and the variables above. A
`Dockerfile` and a `fly.toml` ship as starting points. [docs/hosting.md](docs/hosting.md)
is the guide: a container on any host, Fly.io step by step, or plain Python behind a proxy.

## AI

Stage 2 makes one model call per record and stores the validated answer with the record.
Stages 1 and 3 are rules. Any OpenAI-compatible chat endpoint works: OpenRouter by default,
Anthropic or OpenAI direct, or a local model. [docs/model.md](docs/model.md) has the
options, the prompt and what happens when a call fails.

Coding agents read [AGENTS.md](AGENTS.md). `CLAUDE.md` imports it for Claude Code.

## Repository layout

```
AGENTS.md        instructions for coding agents; CLAUDE.md imports it
AUTHORS.md       who built it
config/          Django settings, URLs, WSGI
docs/            the spec and the guides
prototype/       the first, static prototype from the hackathon
reference/       country, region and income data the tool reads at run time
review.yaml      the review as data: outcomes, certainty, closed lists
rubric.yaml      every rule: fields, criteria, thresholds, overrides
signal_tool/     the pipeline, three stages, no Django
testdata/        the sample records, the hand sheet and the stored model answers
web/             the Django app: models, the tagging thread, views, templates
Dockerfile       the container image; fly.toml is one way to run it
```

## Docs

- [docs/architecture.md](docs/architecture.md) — how it all works: stages, tables, pages, threads, data contracts.
- [docs/hosting.md](docs/hosting.md) — how to host it.
- [docs/model.md](docs/model.md) — the model call and the provider options.
- [docs/spec.md](docs/spec.md) — the spec: information flow, decision tree, field dictionary, rubric v0.
- [prototype/README.md](prototype/README.md) — the first prototype.

## Background

Update Signal was built at the DESTINY hackathon in Cape Town on 17 and 18 September 2026.
The first prototype from the hackathon lives under [prototype/](prototype/README.md).
[AUTHORS.md](AUTHORS.md) lists who built it.
