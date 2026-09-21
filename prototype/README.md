# The first prototype

`living-evidence-review/` is the first idea, added on 17 September 2026 (commit `00c634b`),
the first day of the DESTINY hackathon. It is a React and tRPC app scaffolded on the Manus
platform, and it expects that runtime: its own auth, database and debug hooks live under
`client/src/_core/` and `server/_core/`.

It is static. The records, the outcomes and the scoring rules are TypeScript constants in
`server/reviewData.ts` and `server/reviewEngine.ts`. Nothing is uploaded, and a rule change
is a code change.

The Django tool at the repo root replaced it. `manage.py test` does not cover this folder,
and nothing in the tool imports it. It stays as the record of where the idea started.
