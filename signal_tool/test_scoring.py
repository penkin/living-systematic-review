import unittest
from pathlib import Path

from signal_tool.tagging import load_rules
from signal_tool.scoring import score

RULES = load_rules(str(Path(__file__).resolve().parents[1] / "rubric.yaml"))

# review.yaml allowed_values.study_design
ALL_DESIGNS = ["SR", "RCT", "non-randomised", "cohort", "cross-sectional",
               "qualitative", "modelling", "other"]


class CriterionDTests(unittest.TestCase):
    def test_systematic_review_and_randomised_trial_score_two(self):
        self.assertEqual(score("D", "SR", RULES), 2)
        self.assertEqual(score("D", "RCT", RULES), 2)

    def test_every_other_design_scores_zero(self):
        for design in ALL_DESIGNS:
            if design in ("SR", "RCT"):
                continue
            with self.subTest(design=design):
                self.assertEqual(score("D", design, RULES), 0)

    def test_there_is_no_middle_score(self):
        self.assertEqual({score("D", d, RULES) for d in ALL_DESIGNS}, {0, 2})

    def test_an_unknown_design_scores_zero(self):
        self.assertEqual(score("D", "case report", RULES), 0)
        self.assertEqual(score("D", "", RULES), 0)
        self.assertEqual(score("D", None, RULES), 0)

    def test_the_score_never_exceeds_the_stated_maximum(self):
        rule = RULES["criteria"]["D"]
        self.assertTrue(all(v <= rule["max"] for v in rule["scores"].values()))
