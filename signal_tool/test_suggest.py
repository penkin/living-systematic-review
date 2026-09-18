import csv
import json
import unittest
from pathlib import Path

import yaml

from signal_tool.suggest import asked_fields, compile_prompt, parse_json, suggest, validate

ROOT = Path(__file__).resolve().parents[1]
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))
RULES = yaml.safe_load((ROOT / "rubric.yaml").read_text(encoding="utf-8"))
FIXTURES = Path(__file__).resolve().parent / "testdata" / "model"


def cards():
    with (ROOT / "cards.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

RECORD = {"record_id": "SYN-999", "title": "Heat and sleep in Accra", "abstract": "A cohort of 40 adults in Accra."}
GOOD = {
    "study_design": "cohort", "relevance": "Direct", "outcome_touched": "O1",
    "intervention_tested": "No", "answers_question": "Yes",
    "equity_level": "None", "equity_factors": [], "harm_reported": "No",
    "new_intervention_class": "No", "new_class_name": "", "policy_relevance": "Some",
    "countries_iso3": ["GHA"], "sample_size": 40,
    "evidence": {f["id"]: "" for f in asked_fields(RULES)},
}


class FakeClient:
    """Stands in for build_client(). Records the call, returns GOOD inside a code fence."""

    def __init__(self):
        self.calls = []

    def __call__(self, system, user, schema):
        self.calls.append((system, user, schema))
        return "```json\n" + json.dumps(GOOD) + "\n```"


def RaisingClient():
    def complete(system, user, schema):
        raise AssertionError("the model was called")

    return complete


class FixtureClient:
    """Serves the recorded response for the record named in the prompt, by record_id only."""

    def __init__(self):
        self.calls = 0

    def __call__(self, system, user, schema):
        self.calls += 1
        record_id = user.splitlines()[0].removeprefix("record_id: ")
        hits = sorted(FIXTURES.glob(f"{record_id}-*.json"))
        if not hits:
            raise LookupError(f"no fixture for {record_id}")
        return hits[0].read_text(encoding="utf-8")


class SuggestTests(unittest.TestCase):
    def test_every_card_has_a_fixture_that_validates(self):
        client = FixtureClient()
        for record in cards():
            with self.subTest(record=record["record_id"]):
                tags = suggest(record, REVIEW, RULES, client)
                self.assertTrue(tags["model_version"])
                self.assertEqual(tags["validation_errors"], [])
        self.assertEqual(client.calls, 34)

    def test_calls_the_client_once_with_the_schema(self):
        client = FakeClient()
        tags = suggest(RECORD, REVIEW, RULES, client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(tags["study_design"], "cohort")
        system, user, schema = client.calls[0]
        self.assertIn("Review question", system)
        self.assertTrue(user.startswith("record_id: SYN-999\n"))
        self.assertEqual((system, schema), compile_prompt(REVIEW, RULES))

    def test_a_client_error_propagates(self):
        with self.assertRaises(LookupError):
            suggest(RECORD, REVIEW, RULES, FixtureClient())


class ValidateTests(unittest.TestCase):
    def test_good_values_pass_untouched(self):
        out = validate(GOOD, RECORD, REVIEW, RULES)
        self.assertEqual(out["validation_errors"], [])
        self.assertEqual(out["outcome_touched"], "O1")
        self.assertEqual(out["model_status"], "ok")

    def test_stray_values_become_untagged_and_are_logged(self):
        bad = dict(GOOD, study_design="case report", outcome_touched="O42", harm_reported="Maybe",
                   equity_level="Lots", equity_factors=["Age", "Hair colour"],
                   countries_iso3=["Ghana", "GHA"], sample_size="forty")
        out = validate(bad, RECORD, REVIEW, RULES)
        self.assertIsNone(out["study_design"])
        self.assertEqual(out["outcome_touched"], "NONE")
        self.assertIsNone(out["harm_reported"])
        self.assertIsNone(out["equity_level"])
        self.assertEqual(out["equity_factors"], ["Age"])
        self.assertEqual(out["countries_iso3"], ["Ghana", "GHA"])
        self.assertIsNone(out["sample_size"])
        self.assertEqual(len(out["validation_errors"]), 4)

    def test_evidence_must_be_verbatim(self):
        data = dict(GOOD, evidence=dict(GOOD["evidence"], study_design="A cohort of 40 adults", relevance="made up"))
        out = validate(data, RECORD, REVIEW, RULES)
        self.assertEqual(out["evidence"]["study_design"], "A cohort of 40 adults")
        self.assertEqual(out["evidence"]["relevance"], "")
        self.assertEqual(out["evidence_missing"], ["relevance"])

    def test_parse_json_strips_fences_and_preamble(self):
        self.assertEqual(parse_json('Here you go:\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_compile_prompt_asks_for_every_model_field(self):
        system, schema = compile_prompt(REVIEW, RULES)
        asked = [f["id"] for f in RULES["fields"] if f["source"] in ("model", "review")]
        self.assertEqual(schema["required"], asked + ["evidence"])
        self.assertEqual(list(schema["properties"]["evidence"]["properties"]), asked)
        self.assertEqual(schema["properties"]["outcome_touched"]["enum"][-1], "NONE")
        self.assertEqual(schema["properties"]["equity_factors"]["items"]["enum"], REVIEW["allowed_values"]["progress_plus"])
        self.assertEqual(schema["properties"]["countries_iso3"], {"type": "array", "items": {"type": "string"}})
        self.assertEqual(schema["properties"]["sample_size"], {"type": ["integer", "null"]})
        self.assertIn(REVIEW["review_question"].strip(), system)
        self.assertIn("- harm_reported: Yes only if an adverse event or harm is a reported finding.", system)
        self.assertNotIn("record_type", system)
