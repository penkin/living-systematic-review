# The model call

Stage 2 makes one model call per record. Stages 1 and 3 never call a model, so a change of
model changes the tags a reviewer is offered, never the rules that score them.

## The call

`signal_tool/suggest.py`. `build_client()` returns a function that posts one
OpenAI-compatible chat completion with the stdlib `urllib`. No provider SDK is installed.

- Endpoint: `OPENROUTER_BASE_URL` + `/chat/completions`. Default `https://openrouter.ai/api/v1`.
- Auth: `Authorization: Bearer <OPENROUTER_API_KEY>`.
- Body: `model` from `SIGNAL_MODEL`, one system message and one user message,
  `response_format: {"type": "json_object"}`, `max_tokens: 1024`.
- The answer schema goes into the system text, not into a strict `json_schema` response
  format. Some OpenRouter models reject the strict format with a bare 400. `validate` does
  the enforcing.
- Timeout 120 seconds per call. `SIGNAL_CONCURRENCY` calls run side by side, default 8.
- `parse_json` takes the first `{` to the last `}` of the reply, so a code fence or a line
  of preamble does no harm.

## Choosing a provider

Any endpoint that speaks OpenAI chat completions works. The key variable is named
`OPENROUTER_API_KEY` for every provider. The spec, section 10, asks for a low-cost,
offline-friendly tool: a Haiku-class or a local 8B model is enough for the tagging.

| Provider | `OPENROUTER_BASE_URL` | `SIGNAL_MODEL`, for example | Notes |
|---|---|---|---|
| OpenRouter, the default | `https://openrouter.ai/api/v1` | `anthropic/claude-haiku-4.5` | One key, many models. The stored test fixtures came from this pairing. |
| Anthropic direct | `https://api.anthropic.com/v1` | `claude-haiku-4-5` | Anthropic's OpenAI compatibility layer. It accepts the Bearer key. It ignores `response_format`; the schema in the system text still steers the reply, and `parse_json` strips anything around the object. Anthropic calls the layer a test path, not a production one. |
| OpenAI direct | `https://api.openai.com/v1` | a small chat model, for example `gpt-4o-mini` | |
| Ollama, local | `http://localhost:11434/v1` | the model you pulled, for example `llama3.1:8b` | Set `OPENROUTER_API_KEY` to any non-empty value. The tool refuses to tag without one. |
| LM Studio, local | `http://localhost:1234/v1` | the id of the loaded model | Same. |

Switch providers by changing the two variables and restarting. Old runs keep their stored
responses and the name of the model that made them.

## The prompt

`compile_prompt(review, rules)` builds the system text and the answer schema from the
rubric's `fields` list. Only a field with source `model` or `review` is asked for
(`asked_fields`). A `values` list makes a closed list, `type: list` takes several values,
`type: number` an integer or null, else free text. The system text names the review
question, the outcomes with their ids, the out-of-scope topics, the intervention classes
already in the review, and one sentence per field from the field's `prompt` or `label`. The
user turn is the record's columns, `record_id` first.

The model returns one flat JSON object, one key per field, plus an `evidence` object with
one verbatim phrase from the title or abstract per field. The page at
`rubrics/<uuid>/prompt/` shows the compiled text and schema for any saved rubric.

`PROMPT_VERSION` (today `p3`), the model name and the date are added to every response,
stored on the record, and written to `signals.csv` as `prompt_version`, `model_version` and
`prompt_date`.

## Validation

`validate` coerces every answer onto its field's shape.

- A value outside a closed list becomes `None`. The page shows "Not tagged".
- An outcome the review does not have becomes `NONE`.
- A number that is not an integer becomes `None`. A list keeps known values only, in order,
  without duplicates.
- An evidence phrase that does not appear in the title, abstract or location is dropped.
- Every coercion is logged in `validation_errors` and every dropped phrase in
  `evidence_missing`, both stored with the response.

Every model value is `suggested` until a reviewer confirms it. A confirm or an override
never repeats the call: stage 3 re-runs from the stored response and the changed tag.

## Failures

- No `OPENROUTER_API_KEY`: `build_client()` returns None and the upload page refuses the file.
- A call that raises (timeout, HTTP error, unparseable reply) leaves the record listed but
  unscored. `Record.model_status` is `unavailable` and `model_error` holds the exception.
  The run still finishes. There is no retry; upload the file again for a fresh run.

## Test fixtures

`testdata/model/<record_id>-<hash8>.json` holds 34 real responses for `testdata/cards.csv`,
flattened to the compiled shape. `FixtureClient` in `signal_tool/test_suggest.py` serves
them by the `record_id:` line of the user turn, so no test calls the network. Every upload
calls the model live.
