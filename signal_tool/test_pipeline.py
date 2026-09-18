import csv
import io
import unittest
from pathlib import Path

import yaml

from signal_tool.geography import load_reference
from signal_tool.pipeline import COLUMNS, build_row, tags_for, write_csv
from signal_tool.scoring import REASON_WORD_LIMIT
from signal_tool.suggest import suggest
from signal_tool.tagging import load_rules, tag
from signal_tool.test_suggest import FixtureClient, cards

ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(str(ROOT / "rubric.yaml"))
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))
REF = load_reference(ROOT / "reference")

UNKNOWN = {
    "record_id": "SYN-999", "title": "Heat and sleep in Accra", "abstract": "A cohort of 40 adults.",
    "record_type_raw": "Journal article", "year": "2026", "language": "English", "location": "Accra, Ghana",
}


def suggestion(record, client):
    """The stored model response for a record, or None when the call failed."""
    try:
        return suggest(record, REVIEW, client)
    except LookupError:
        return None


def rows_for(records):
    """The three stages in memory: tag the batch, suggest per record, score per record."""
    records = tag(records, RULES, REVIEW, REF)
    client = FixtureClient()
    entries = {r["record_id"]: tags_for(r, suggestion(r, client)) for r in records}
    return records, entries


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        records, entries = rows_for(cards() + [UNKNOWN])
        cls.rows = [build_row(r, entries[r["record_id"]], REVIEW, RULES, REF) for r in records]
        cls.by_id = {r["record_id"]: r for r in cls.rows}

    def test_every_record_is_in_the_output(self):
        self.assertEqual(len(self.rows), 35)
        buffer = io.StringIO()
        write_csv(self.rows, buffer)
        reader = csv.DictReader(io.StringIO(buffer.getvalue()))
        self.assertEqual(tuple(reader.fieldnames), COLUMNS)
        self.assertEqual(len(list(reader)), 35)

    def test_separate_lane_rows_have_a_reason_and_no_level(self):
        for record_id in ("SYN-012", "SYN-016", "SYN-019", "SYN-027", "SYN-031"):
            with self.subTest(record=record_id):
                row = self.by_id[record_id]
                self.assertEqual(row["lane"], "separate")
                self.assertTrue(row["lane_reason"])
                self.assertEqual(row["signal_level"], "")

    def test_a_record_without_a_response_stays_visible_as_unavailable(self):
        row = self.by_id["SYN-999"]
        self.assertEqual(row["model_status"], "unavailable")
        self.assertEqual(row["signal_level"], "")
        self.assertEqual(row["countries"], ["GHA"])

    def test_seeded_cases(self):
        self.assertEqual(self.by_id["SYN-022"]["signal_level"], "HIGH")
        self.assertIn("harm", self.by_id["SYN-022"]["override_triggered"])
        self.assertIn("absent_context", self.by_id["SYN-021"]["override_triggered"])
        self.assertTrue(self.by_id["SYN-013"]["out_of_region"])
        self.assertEqual(self.by_id["SYN-013"]["signal_level"], "MODERATE")
        self.assertTrue(self.by_id["SYN-029"]["scope_question"])
        self.assertTrue(self.by_id["SYN-004"]["scope_question"])
        self.assertTrue(self.by_id["SYN-023"]["non_english"])
        self.assertEqual(self.by_id["SYN-014"]["lmic_setting"], "Yes")

    def test_model_countries_fill_the_rule_gap(self):
        # "Dar es Salaam, Tanzania" never matches the ISO name; the model code does.
        row = next(r for r in self.rows if "Tanzania" in (r["location"] or ""))
        self.assertIn("TZA", row["countries"])

    def test_every_reason_fits_the_limit(self):
        for row in self.rows:
            with self.subTest(record=row["record_id"]):
                self.assertLessEqual(len(str(row["signal_reason"]).split()), REASON_WORD_LIMIT)
                if row["signal_reason"]:
                    self.assertTrue(row["signal_reason"][0].isupper(), row["signal_reason"])

    def test_version_fields_are_filled(self):
        row = self.by_id["SYN-001"]
        self.assertEqual(row["rubric_version"], RULES["rubric_version"])
        self.assertTrue(row["model_version"])
        self.assertEqual(row["reference_date"], REF["date"])


class RescoreTests(unittest.TestCase):
    """Stage 3 re-runs from the stored entry alone. No client is in reach here."""

    @classmethod
    def setUpClass(cls):
        cls.records, cls.entries = rows_for(cards())
        cls.by_id = {r["record_id"]: r for r in cls.records}

    def score(self, record_id, entry):
        return build_row(self.by_id[record_id], entry, REVIEW, RULES, REF)

    def test_an_override_rescores_from_the_stored_entry(self):
        entry = self.entries["SYN-003"]
        self.assertNotEqual(self.score("SYN-003", entry)["signal_level"], "HIGH")
        entry["tags"]["harm_reported"] = {"value": "Yes", "status": "overridden", "evidence": ""}
        self.assertEqual(self.score("SYN-003", entry)["signal_level"], "HIGH")

    def test_overriding_record_type_moves_the_lane(self):
        entry = self.entries["SYN-031"]
        entry["tags"]["record_type"] = {"value": "journal_article", "status": "overridden", "evidence": ""}
        row = self.score("SYN-031", entry)
        self.assertEqual(row["lane"], "signal")
        self.assertIn(row["signal_level"], ("LOW", "MODERATE", "HIGH"))
