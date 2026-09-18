import csv
import json
import unittest
from pathlib import Path

import yaml

from signal_tool.suggest import EVIDENCE_FIELDS, output_schema, parse_json, suggest, validate

ROOT = Path(__file__).resolve().parents[1]
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))
FIXTURES = Path(__file__).resolve().parent / "testdata" / "model"


def cards():
    with (ROOT / "cards.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

RECORD = {"record_id": "SYN-999", "title": "Heat and sleep in Accra", "abstract": "A cohort of 40 adults in Accra."}
GOOD = {
    "study_design": "cohort", "relevance": "Direct", "outcome_touched": "O1",
    "intervention_tested": "No", "answers_question": "Yes",
    "equity_relevance": {"level": "None", "factors": []}, "harm_reported": "No",
    "new_intervention_class": {"value": "No", "class_name": ""}, "policy_relevance": "Some",
    "countries_iso3": ["GHA"], "sample_size": 40,
    "evidence": {f: "" for f in EVIDENCE_FIELDS},
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
                tags = suggest(record, REVIEW, client)
                self.assertTrue(tags["model_version"])
                self.assertEqual(tags["validation_errors"], [])
        self.assertEqual(client.calls, 34)

    def test_calls_the_client_once_with_the_schema(self):
        client = FakeClient()
        tags = suggest(RECORD, REVIEW, client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(tags["study_design"], "cohort")
        system, user, schema = client.calls[0]
        self.assertIn("Review question", system)
        self.assertTrue(user.startswith("record_id: SYN-999\n"))
        self.assertEqual(schema, output_schema(REVIEW))

    def test_a_client_error_propagates(self):
        with self.assertRaises(LookupError):
            suggest(RECORD, REVIEW, FixtureClient())


class ValidateTests(unittest.TestCase):
    def test_good_values_pass_untouched(self):
        out = validate(GOOD, RECORD, REVIEW)
        self.assertEqual(out["validation_errors"], [])
        self.assertEqual(out["outcome_touched"], "O1")
        self.assertEqual(out["model_status"], "ok")

    def test_stray_values_take_the_safe_default_and_are_logged(self):
        bad = dict(GOOD, study_design="case report", outcome_touched="O42", harm_reported="Maybe",
                   equity_relevance={"level": "Lots", "factors": ["Age", "Hair colour"]},
                   countries_iso3=["Ghana", "GHA"], sample_size="forty")
        out = validate(bad, RECORD, REVIEW)
        self.assertEqual(out["study_design"], "other")
        self.assertEqual(out["outcome_touched"], "NONE")
        self.assertEqual(out["harm_reported"], "Unclear")
        self.assertEqual(out["equity_relevance"], {"level": "None", "factors": ["Age"]})
        self.assertEqual(out["countries_iso3"], ["GHA"])
        self.assertIsNone(out["sample_size"])
        self.assertEqual(len(out["validation_errors"]), 4)

    def test_evidence_must_be_verbatim(self):
        data = dict(GOOD, evidence=dict(GOOD["evidence"], study_design="A cohort of 40 adults", relevance="made up"))
        out = validate(data, RECORD, REVIEW)
        self.assertEqual(out["evidence"]["study_design"], "A cohort of 40 adults")
        self.assertEqual(out["evidence"]["relevance"], "")
        self.assertEqual(out["evidence_missing"], ["relevance"])

    def test_parse_json_strips_fences_and_preamble(self):
        self.assertEqual(parse_json('Here you go:\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_schema_enumerates_the_review_lists(self):
        schema = output_schema(REVIEW)
        self.assertIn("NONE", schema["properties"]["outcome_touched"]["enum"])
        self.assertEqual(schema["properties"]["study_design"]["enum"], REVIEW["allowed_values"]["study_design"])
