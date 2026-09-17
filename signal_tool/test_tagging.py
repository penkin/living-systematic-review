import unittest
from pathlib import Path

from signal_tool.tagging import classify, load_rules

RULES = load_rules(str(Path(__file__).resolve().parents[1] / "rubric.yaml"))


def lane_of(**record):
    return classify(record, RULES)


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

    def test_preprint_still_scores_until_a_duplicate_is_found(self):
        record_type, lane, _ = lane_of(record_type_raw="Preprint")
        self.assertEqual(record_type, "preprint")
        self.assertEqual(lane, "signal")

    def test_plain_article_scores(self):
        self.assertEqual(lane_of(record_type_raw="Journal article")[1], "signal")

    def test_unknown_type_falls_back_to_the_default(self):
        record_type, lane, _ = lane_of(title="Heat and mortality in Accra")
        self.assertEqual(record_type, "journal_article")
        self.assertEqual(lane, "signal")
