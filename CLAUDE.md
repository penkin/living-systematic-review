# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This is a specification and a dataset, not an application. Nothing is implemented
yet. There is no build, no test, no lint, no package manager, and no git repository.

When you write the first code, add the run and test commands to this section.

## What the tool is

A living systematic review gets new records. The tool tags each record, looks up how
certain the review already is about the outcome the record touches, and ranks it
High / Moderate / Low with a reason of fifteen words or fewer. The reviewer decides.
The tool suggests.

## Hard rules

- Never include or exclude a study. Never decide that the review needs an update.
- Every model output is `suggested` until a human confirms it. Five fields carry a
  confirm/override control: `record_type`, `relevance`, `outcome_touched`,
  `harm_reported`, `new_intervention_class`.
- Low records stay visible. Deprioritise them, never hide them.
- Never infer outcome certainty. Look it up in `review.yaml`.
- Never hardcode geography. Countries, regions, and income groups come from
  `reference/` and from the World Bank API.
- Never require a network connection at demo time. Cache every model response.
- Never write the rubric, the thresholds, or the overrides into code. The review team
  edits them without a developer present.
- The open questions in `SPEC.md` section 4 are configuration switches, not code
  branches: `promote_large_studies_on_moderate`, `out_of_region_cap`,
  `out_of_scope_handling`, `certainty_inverted`.

## Pipeline

1. **Stage 1, deterministic.** `record_type`, `lane`, countries by exact ISO 3166
   name match, recency, in-batch duplicates. Separate-lane types leave the pipeline
   and never get a signal level.
2. **Stage 2, suggested.** One cached model call per record, closed lists in and
   validated JSON out, each value with a verbatim evidence phrase. The geography
   resolver then unions rule-matched and model-inferred countries.
3. **Stage 3, lookup and score.** Certainty lookup from `review.yaml`, criteria A–G
   to a total of 0–15, overrides, threshold, then the reason template.
4. **Output.** `signals.csv`, a flat file a reviewer sorts in a spreadsheet, plus
   blank reviewer columns and the version fields.

Read `SPEC.md` section 4 before you change the decision tree. Read section 6 before
you change the rubric. Read section 5 to find which stage produces a field.

## Data contracts

- `cards.csv` — 34 records, `SYN-001` to `SYN-034`. Columns: `record_id`, `title`,
  `abstract`, `record_type_raw`, `year`, `language`, `location`. Only the first three
  are required for a future import; Covidence, Rayyan, and EPPI-Reviewer supply them.
  The set is seeded to trip the equity test: one French record, one 2025 record, one
  retracted article, one protocol, one preprint, one commentary, one conference
  abstract.
- `review.yaml` — the review as data. Nine outcomes `O1`–`O9`, each with `certainty`
  and `n_studies`. `absent_contexts` uses ISO3 codes or UN M49 region labels, so the
  absent-context override matches mechanically. The file also holds
  `out_of_scope_outcomes`, `intervention_classes_represented`, and `allowed_values`,
  the closed lists the tagger must pick from.
- `reference/iso3166_regions.csv` — UN M49 `region` and `sub-region` per country.
  World Bank income groups come from
  `https://api.worldbank.org/v2/country?format=json&per_page=400`, field
  `incomeLevel`. Record the download date; `SPEC.md` expects a dated `METADATA.json`
  beside the reference data.
- `docs/` — the three source documents, in PDF and DOCX. They are binary. Use the
  `pdf` or `docx` skill to read them. `SPEC.md` already carries their content.

## Known gaps

Do not pick a side on either of these silently.

- Criterion A has a 0–3 range. `review.yaml` gives `relevance` three values: Direct,
  Partial, Not relevant. The mapping of "Mostly relevant" = 2 is undecided
  (`SPEC.md:177`).
- `review.yaml` carries no `absent_contexts` for O1, O2, O3, O4, O6, or O9, and no
  `evidence_contexts` beyond O1. The absent-context override fires on a subset of
  outcomes only.
