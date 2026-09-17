import csv
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from signal_tool.geography import load_reference
from signal_tool.pipeline import COLUMNS, read_tags, rescore, run, write_tags
from signal_tool.scoring import REASON_WORD_LIMIT
from signal_tool.tagging import load_rules
from signal_tool.test_suggest import RaisingClient

ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(str(ROOT / "rubric.yaml"))
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))
REF = load_reference(ROOT / "reference")
SHARED = ROOT / "cache" / "model"

UNKNOWN = '"SYN-999","Heat and sleep in Accra","A cohort of 40 adults.","Journal article","2026","English","Accra, Ghana"\n'


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = Path(tempfile.mkdtemp())
        cards = (ROOT / "cards.csv").read_text(encoding="utf-8-sig")
        (cls.run_dir / "cards.csv").write_text(cards + UNKNOWN, encoding="utf-8")
        cls.rows = run(cls.run_dir, REVIEW, RULES, REF, SHARED, client=None)
        cls.by_id = {r["record_id"]: r for r in cls.rows}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.run_dir)

    def test_every_record_is_in_the_output(self):
        self.assertEqual(len(self.rows), 35)
        with (self.run_dir / "signals.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(tuple(reader.fieldnames), COLUMNS)
            self.assertEqual(len(list(reader)), 35)

    def test_separate_lane_rows_have_a_reason_and_no_level(self):
        for record_id in ("SYN-012", "SYN-016", "SYN-019", "SYN-027", "SYN-031"):
            with self.subTest(record=record_id):
                row = self.by_id[record_id]
                self.assertEqual(row["lane"], "separate")
                self.assertTrue(row["lane_reason"])
                self.assertEqual(row["signal_level"], "")

    def test_a_record_without_a_cache_stays_visible_as_unavailable(self):
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
    def setUp(self):
        self.run_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run_dir)
        shutil.copyfile(ROOT / "cards.csv", self.run_dir / "cards.csv")
        run(self.run_dir, REVIEW, RULES, REF, SHARED, client=RaisingClient())

    def test_an_override_rescores_without_a_model_call_or_a_new_cache_file(self):
        tagged = read_tags(self.run_dir)
        before = {r["record_id"]: r for r in rescore(self.run_dir, REVIEW, RULES, REF)}
        self.assertNotEqual(before["SYN-003"]["signal_level"], "HIGH")
        tagged["SYN-003"]["tags"]["harm_reported"] = {"value": "Yes", "status": "overridden", "evidence": ""}
        write_tags(self.run_dir, tagged)
        cache_before = sorted(p.name for p in (self.run_dir / "model").iterdir())
        after = {r["record_id"]: r for r in rescore(self.run_dir, REVIEW, RULES, REF)}
        self.assertEqual(after["SYN-003"]["signal_level"], "HIGH")
        self.assertEqual(sorted(p.name for p in (self.run_dir / "model").iterdir()), cache_before)

    def test_overriding_record_type_moves_the_lane(self):
        tagged = read_tags(self.run_dir)
        tagged["SYN-031"]["tags"]["record_type"] = {"value": "journal_article", "status": "overridden", "evidence": ""}
        write_tags(self.run_dir, tagged)
        row = {r["record_id"]: r for r in rescore(self.run_dir, REVIEW, RULES, REF)}["SYN-031"]
        self.assertEqual(row["lane"], "signal")
        self.assertIn(row["signal_level"], ("LOW", "MODERATE", "HIGH"))
