import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from signal_tool.suggest import EVIDENCE_FIELDS, cache_key, output_schema, suggest, validate

ROOT = Path(__file__).resolve().parents[1]
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))
SHARED = ROOT / "cache" / "model"

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
    """Stands in for anthropic.Anthropic. Records the call, returns GOOD as JSON."""

    def __init__(self):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(GOOD))])


class RaisingClient:
    def __init__(self):
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        raise AssertionError("the model was called")


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)

    def cards(self):
        with (ROOT / "cards.csv").open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_every_card_has_a_stub_and_none_calls_the_model(self):
        for record in self.cards():
            with self.subTest(record=record["record_id"]):
                tags = suggest(record, REVIEW, self.run / "model", SHARED, client=RaisingClient())
                self.assertEqual(tags["model_version"], "stub")
                self.assertEqual(tags["validation_errors"], [])
                self.assertEqual(tags["evidence_missing"], [])
        self.assertEqual(len(list((self.run / "model").iterdir())), 34)

    def test_a_miss_without_a_client_returns_none(self):
        self.assertIsNone(suggest(RECORD, REVIEW, self.run / "model", SHARED))
        self.assertFalse((self.run / "model").exists())

    def test_a_miss_with_a_client_calls_once_and_caches(self):
        client = FakeClient()
        first = suggest(RECORD, REVIEW, self.run / "model", self.run / "shared", client)
        second = suggest(RECORD, REVIEW, self.run / "model", self.run / "shared", RaisingClient())
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(first["study_design"], second["study_design"], "cohort")
        call = client.calls[0]
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        self.assertIn("Review question", call["system"])
        self.assertTrue((self.run / "model" / cache_key(RECORD)).is_file())

    def test_the_cache_key_changes_with_the_text(self):
        changed = dict(RECORD, abstract="Different abstract.")
        self.assertNotEqual(cache_key(RECORD), cache_key(changed))
        self.assertTrue(cache_key(RECORD).startswith("SYN-999-"))


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

    def test_schema_enumerates_the_review_lists(self):
        schema = output_schema(REVIEW)
        self.assertIn("NONE", schema["properties"]["outcome_touched"]["enum"])
        self.assertEqual(schema["properties"]["study_design"]["enum"], REVIEW["allowed_values"]["study_design"])
