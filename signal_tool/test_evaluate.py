import unittest

from signal_tool.evaluate import agreement, equity, parse_handsort, regret
from signal_tool.test_scoring import RULES


def row(record_id, level, score, **extra):
    base = {"record_id": record_id, "signal_level": level, "signal_score": score, "lmic_setting": "Yes",
            "non_english": False, "study_design": "cohort", "sample_size": 100, "record_type": "journal_article",
            "relevance": "Direct", "outcome_touched": "O1", "harm_reported": "No", "new_intervention_class": "No"}
    return {**base, **extra}


ROWS = [
    row("R1", "HIGH", 13),
    row("R2", "MODERATE", 8, non_english=True),
    row("R3", "LOW", 3, sample_size=5000, lmic_setting="No"),
    row("R4", "", "", lane="separate"),
]


class EquityTests(unittest.TestCase):
    def test_groups_scored_rows_only(self):
        out = equity(ROWS, RULES)
        by_language = {g["group"]: g for g in out["non_english"]}
        self.assertEqual(by_language["Yes"]["n"], 1)
        self.assertEqual(by_language["No"]["n"], 2)
        self.assertEqual(by_language["No"]["mean_score"], 8.0)
        self.assertEqual(by_language["No"]["share_high"], 0.5)

    def test_size_bucket_uses_the_rubric_threshold(self):
        groups = {g["group"] for g in equity(ROWS, RULES)["sample_size"]}
        self.assertEqual(groups, {"n < 1000", "n >= 1000"})


class HandsortTests(unittest.TestCase):
    HANDSORT = {"R1": "HIGH", "R2": "HIGH", "R3": "LOW", "R4": "HIGH"}

    def test_parse_requires_both_columns(self):
        self.assertEqual(parse_handsort("record_id,hand_level\nR1, high\n"), {"R1": "HIGH"})
        with self.assertRaises(ValueError):
            parse_handsort("record_id,level\nR1,HIGH\n")

    def test_agreement_crosstab_and_records(self):
        out = agreement(ROWS, self.HANDSORT, RULES)
        self.assertEqual(out["table"]["HIGH"]["HIGH"], 1)
        self.assertEqual(out["table"]["MODERATE"]["HIGH"], 1)
        self.assertEqual(out["table"][""]["HIGH"], 1)
        self.assertEqual([r["agree"] for r in out["records"]], [True, False, True, False])
        self.assertEqual(out["records"][0]["harm_reported"], "No")

    def test_regret_lists_hand_high_outside_the_top_n(self):
        missed = regret(ROWS, self.HANDSORT, top_n=1)
        self.assertEqual([m["record_id"] for m in missed], ["R2", "R4"])
        self.assertEqual(missed[0]["rank"], 2)
        self.assertIsNone(missed[1]["rank"])
        self.assertEqual(regret(ROWS, self.HANDSORT, top_n=10), [m for m in regret(ROWS, self.HANDSORT, 10) if m["record_id"] == "R4"])
