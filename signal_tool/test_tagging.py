import csv
import unittest
from pathlib import Path

import yaml

from signal_tool.geography import load_reference
from signal_tool.tagging import classify, load_rules, tag

ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(str(ROOT / "rubric.yaml"))
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))
REF = load_reference(ROOT / "reference")


def lane_of(**record):
    return classify(record, RULES)


def tagged_cards():
    with (ROOT / "cards.csv").open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    return {r["record_id"]: r for r in tag(records, RULES, REVIEW, REF)}


class ClassifyTests(unittest.TestCase):
    def test_retracted_leaves_the_signal_lane(self):
        record_type, lane, reason = lane_of(record_type_raw="Journal article (retracted)")
        self.assertEqual(record_type, "retracted")
        self.assertEqual(lane, "separate")
        self.assertTrue(reason)

    def test_retracted_is_caught_without_the_type_column(self):
        # Covidence and Rayyan exports need not supply record_type_raw.
        _, lane, _ = lane_of(title="RETRACTED: Ambient temperature and stroke admissions in Lagos")
        self.assertEqual(lane, "separate")

    def test_retracted_beats_journal_article_in_the_same_string(self):
        record_type, _, _ = lane_of(record_type_raw="Journal article (retracted)")
        self.assertEqual(record_type, "retracted")

    def test_protocol_commentary_and_conference_abstract_leave_the_lane(self):
        for raw in ("Study protocol", "Commentary", "Conference abstract"):
            with self.subTest(raw=raw):
                self.assertEqual(lane_of(record_type_raw=raw)[1], "separate")

    def test_a_lone_preprint_still_scores(self):
        record_type, lane, _ = lane_of(record_type_raw="Preprint")
        self.assertEqual(record_type, "preprint")
        self.assertEqual(lane, "signal")

    def test_plain_article_scores(self):
        self.assertEqual(lane_of(record_type_raw="Journal article")[1], "signal")

    def test_unknown_type_falls_back_to_the_default(self):
        record_type, lane, _ = lane_of(title="Heat and mortality in Accra")
        self.assertEqual(record_type, "journal_article")
        self.assertEqual(lane, "signal")


class StageOneOnCardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = tagged_cards()

    def test_the_preprint_duplicate_leaves_the_lane_and_the_article_stays(self):
        preprint, article = self.cards["SYN-019"], self.cards["SYN-005"]
        self.assertEqual(preprint["lane"], "separate")
        self.assertEqual(preprint["lane_reason"], "Preprint duplicate of SYN-005")
        self.assertTrue(preprint["is_duplicate"])
        self.assertEqual(article["lane"], "signal")
        self.assertFalse(article["is_duplicate"])

    def test_only_the_seeded_pair_is_a_duplicate(self):
        self.assertEqual([k for k, r in self.cards.items() if r["is_duplicate"]], ["SYN-019"])

    def test_five_records_sit_in_the_separate_lane(self):
        separate = sorted(k for k, r in self.cards.items() if r["lane"] == "separate")
        self.assertEqual(separate, ["SYN-012", "SYN-016", "SYN-019", "SYN-027", "SYN-031"])

    def test_secondary_report_is_flagged_not_routed(self):
        self.assertTrue(self.cards["SYN-028"]["secondary_report"])
        self.assertEqual(self.cards["SYN-028"]["lane"], "signal")
        self.assertFalse(self.cards["SYN-014"]["secondary_report"])

    def test_the_french_record_is_non_english(self):
        self.assertTrue(self.cards["SYN-023"]["non_english"])
        self.assertFalse(self.cards["SYN-001"]["non_english"])

    def test_recency_follows_the_update_window(self):
        self.assertEqual(self.cards["SYN-003"]["recency_score"], 1)
        self.assertEqual(tag([{"record_id": "X", "year": "2019"}], RULES, REVIEW, REF)[0]["recency_score"], 0)

    def test_countries_by_exact_iso_name(self):
        self.assertEqual(self.cards["SYN-021"]["countries_rule"], ["BFA"])
        # "Tanzania" is not the ISO name. Stage 2 fills this gap.
        self.assertEqual(self.cards["SYN-009"]["countries_rule"], [])
