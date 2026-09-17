import copy
import unittest
from pathlib import Path

import yaml

from signal_tool.scoring import REASON_WORD_LIMIT, score, score_record
from signal_tool.tagging import load_rules

ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(str(ROOT / "rubric.yaml"))
REVIEW = yaml.safe_load((ROOT / "review.yaml").read_text(encoding="utf-8"))

# review.yaml allowed_values.study_design
ALL_DESIGNS = ["SR", "RCT", "non-randomised", "cohort", "cross-sectional",
               "qualitative", "modelling", "other"]

# A relevant randomised trial in Cape Town on cardiovascular mortality, an outcome
# with no absent context. Scores A3 B2 C1 D2 E2 F1 G2 = 13, HIGH.
TRIAL = {
    "study_design": "RCT", "relevance": "Direct", "outcome_touched": "O3",
    "intervention_tested": "Yes", "answers_question": "Yes", "lmic_setting": "Yes",
    "equity_level": "Group included", "harm_reported": "No", "new_intervention_class": "No",
    "policy_relevance": "Direct", "recency_score": 1, "is_duplicate": False,
    "countries": ["ZAF"], "country_names": ["South Africa"],
    "regions": ["Africa", "Sub-Saharan Africa", "Southern Africa"], "sample_size": 96,
}


def scored(**changes):
    return score_record({**TRIAL, **changes}, REVIEW, RULES)


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

    def test_an_unknown_design_scores_zero(self):
        self.assertEqual(score("D", "case report", RULES), 0)
        self.assertEqual(score("D", None, RULES), 0)

    def test_no_listed_score_exceeds_its_maximum(self):
        for name, rule in RULES["criteria"].items():
            with self.subTest(criterion=name):
                values = rule["scores"].values() if "scores" in rule else [
                    sum(max(p["scores"].values()) for p in rule["parts"])
                ]
                self.assertTrue(all(v <= rule["max"] for v in values))


class CriterionATests(unittest.TestCase):
    def test_a_sums_three_parts(self):
        self.assertEqual(scored()["A"], 3)
        self.assertEqual(scored(lmic_setting="Mixed")["A"], 2)
        self.assertEqual(scored(lmic_setting="Mixed", intervention_tested="No")["A"], 1)
        self.assertEqual(scored(lmic_setting="No", intervention_tested="No", answers_question="No")["A"], 0)

    def test_b_still_gives_mixed_a_point(self):
        self.assertEqual(scored(lmic_setting="Mixed")["B"], 1)


class ThresholdTests(unittest.TestCase):
    def test_the_trial_is_high(self):
        result = scored()
        self.assertEqual(result["signal_score"], 13)
        self.assertEqual(result["signal_level"], "HIGH")
        self.assertEqual(result["suggested_action"], "Review now")

    def test_a_of_one_caps_at_moderate(self):
        # A1 B2 C1 D2 E2 F1 G2 = 11: on the HIGH line, but A = 1.
        result = scored(intervention_tested="No", answers_question="No")
        self.assertEqual(result["A"], 1)
        self.assertEqual(result["signal_score"], 11)
        self.assertEqual(result["signal_level"], "MODERATE")

    def test_a_of_zero_is_low_and_skips_overrides(self):
        result = scored(intervention_tested="No", answers_question="No", lmic_setting="No",
                        harm_reported="Yes")
        self.assertEqual(result["signal_level"], "LOW")
        self.assertEqual(result["override_triggered"], "")

    def test_moderate_band(self):
        # A2 B0 C0 D0 E1 F1 G2 = 6
        result = scored(lmic_setting="No", equity_level="None", study_design="cohort",
                        policy_relevance="Some", outcome_touched="O3")
        self.assertEqual(result["signal_score"], 6)
        self.assertEqual(result["signal_level"], "MODERATE")

    def test_low_band(self):
        result = scored(lmic_setting="No", equity_level="None", study_design="cohort",
                        policy_relevance="None", outcome_touched="O1", recency_score=0)
        self.assertEqual(result["signal_score"], 3)
        self.assertEqual(result["signal_level"], "LOW")
        self.assertEqual(result["suggested_action"], "Deprioritise")

    def test_a_duplicate_earns_no_recency_point(self):
        self.assertEqual(scored(is_duplicate=True)["F"], 0)


class CertaintyTests(unittest.TestCase):
    def test_g_follows_the_review_not_the_record(self):
        self.assertEqual(scored(outcome_touched="O1")["G"], 1)
        self.assertEqual(scored(outcome_touched="O3")["G"], 2)
        self.assertEqual(scored(outcome_touched="O7")["G"], 3)
        self.assertEqual(scored(outcome_touched="O1")["n_studies"], 14)

    def test_certainty_inverted_zeroes_g(self):
        review = copy.deepcopy(REVIEW)
        review["outcomes"][6]["certainty_inverted"] = True
        result = score_record({**TRIAL, "outcome_touched": "O7"}, review, RULES)
        self.assertEqual(result["G"], 0)
        self.assertEqual(result["outcome_certainty"], "Very low")

    def test_none_is_surfaced_as_a_scope_question(self):
        result = scored(outcome_touched="NONE")
        self.assertTrue(result["scope_question"])
        self.assertEqual(result["G"], 0)
        self.assertEqual(result["outcome_certainty"], "")
        self.assertIn("scope question", result["signal_reason"])
        self.assertNotEqual(result["signal_level"], "LOW")

    def test_suppress_switch_forces_low_but_still_scores(self):
        rules = copy.deepcopy(RULES)
        rules["switches"]["out_of_scope_handling"] = "suppress"
        result = score_record({**TRIAL, "outcome_touched": "NONE"}, REVIEW, rules)
        self.assertEqual(result["signal_level"], "LOW")
        self.assertEqual(result["signal_score"], 11)


class OverrideTests(unittest.TestCase):
    def test_harm_forces_high(self):
        result = scored(study_design="other", equity_level="None", policy_relevance="None",
                        harm_reported="Yes")
        self.assertEqual(result["level_from_threshold"], "MODERATE")
        self.assertEqual(result["signal_level"], "HIGH")
        self.assertEqual(result["override_triggered"], "harm")
        self.assertIn("harm reported", result["signal_reason"])

    def test_new_class_forces_high(self):
        result = scored(study_design="other", new_intervention_class="Yes", policy_relevance="None")
        self.assertEqual(result["signal_level"], "HIGH")
        self.assertEqual(result["override_triggered"], "new_class")

    def test_absent_context_raises_one_level(self):
        # SYN-021 shaped: early warning system, Burkina Faso, O8 absent in Africa.
        result = scored(study_design="non-randomised", equity_level="None", outcome_touched="O8",
                        policy_relevance="Some",
                        countries=["BFA"], country_names=["Burkina Faso"],
                        regions=["Africa", "Sub-Saharan Africa", "Western Africa"])
        self.assertEqual(result["absent_context_hit"], "Yes")
        self.assertEqual(result["level_from_threshold"], "MODERATE")
        self.assertEqual(result["signal_level"], "HIGH")
        self.assertEqual(result["override_triggered"], "absent_context")

    def test_absent_context_matches_the_intermediate_region(self):
        result = scored(outcome_touched="O5", countries=["BFA"], country_names=["Burkina Faso"],
                        regions=["Africa", "Sub-Saharan Africa", "Western Africa"])
        self.assertEqual(result["absent_context_hit"], "Yes")
        self.assertEqual(scored(outcome_touched="O5")["absent_context_hit"], "No")

    def test_raise_stops_at_high(self):
        result = scored(outcome_touched="O7", countries=["ZAF"])
        self.assertEqual(result["signal_level"], "HIGH")


class RegionCapTests(unittest.TestCase):
    def test_out_of_region_caps_at_moderate(self):
        # SYN-013 shaped: Ahmedabad, O8, everything else strong.
        result = scored(study_design="non-randomised", outcome_touched="O8", countries=["IND"],
                        country_names=["India"], regions=["Asia", "Southern Asia"])
        self.assertTrue(result["out_of_region"])
        self.assertEqual(result["signal_level"], "MODERATE")

    def test_unknown_region_is_not_capped(self):
        result = scored(countries=[], country_names=[], regions=[], lmic_setting="Unclear")
        self.assertFalse(result["out_of_region"])

    def test_cap_switch_none_turns_it_off(self):
        rules = copy.deepcopy(RULES)
        rules["switches"]["out_of_region_cap"] = "none"
        tags = {**TRIAL, "countries": ["IND"], "regions": ["Asia"]}
        self.assertEqual(score_record(tags, REVIEW, rules)["signal_level"], "HIGH")


class PromotionTests(unittest.TestCase):
    def test_off_by_default(self):
        result = scored(study_design="cohort", equity_level="None", outcome_touched="O1",
                        sample_size=5000)
        self.assertEqual(result["signal_level"], "MODERATE")

    def test_switch_promotes_a_large_study_on_a_moderate_outcome(self):
        rules = copy.deepcopy(RULES)
        rules["switches"]["promote_large_studies_on_moderate"] = True
        tags = {**TRIAL, "study_design": "cohort", "equity_level": "None", "outcome_touched": "O1",
                "sample_size": 5000}
        self.assertEqual(score_record(tags, REVIEW, rules)["signal_level"], "HIGH")


class ReasonTests(unittest.TestCase):
    def test_reason_names_the_fields(self):
        reason = scored()["signal_reason"]
        self.assertIn("Randomised trial", reason)
        self.assertIn("South Africa", reason)
        self.assertIn("6 studies", reason)
        self.assertIn("low certainty", reason)

    def test_reason_never_exceeds_the_limit(self):
        long_tags = {**TRIAL, "country_names": ["Tanzania, United Republic of", "Mozambique"],
                     "outcome_touched": "O5", "harm_reported": "Yes", "new_intervention_class": "Yes",
                     "countries": ["BFA"], "regions": ["Western Africa"]}
        reason = score_record(long_tags, REVIEW, RULES)["signal_reason"]
        self.assertLessEqual(len(reason.split()), REASON_WORD_LIMIT)


class BreakdownTests(unittest.TestCase):
    def test_detail_rows_match_the_scores_in_order(self):
        result = scored()
        rows = result["criteria_detail"]
        self.assertEqual([r["criterion"] for r in rows], list("ABCDEFG"))
        for row in rows:
            self.assertEqual(row["points"], result[row["criterion"]])
            self.assertTrue(row["help"])
        self.assertEqual(sum(r["points"] for r in rows), result["signal_score"])
        self.assertEqual(result["signal_max"], 15)

    def test_values_are_plain_words(self):
        rows = {r["criterion"]: r["value"] for r in scored()["criteria_detail"]}
        self.assertEqual(rows["D"], "Randomised trial")
        self.assertIn("Tests an intervention: Yes", rows["A"])
        self.assertEqual(rows["G"], "cardiovascular mortality: low certainty from 6 studies")
        self.assertEqual(rows["F"], "Published in the update window")
        duplicate = {r["criterion"]: r["value"] for r in scored(is_duplicate=True)["criteria_detail"]}
        self.assertEqual(duplicate["F"], "Duplicate of another record in this batch")
        untagged = {r["criterion"]: r["value"] for r in scored(study_design=None)["criteria_detail"]}
        self.assertEqual(untagged["D"], "Not tagged")

    def test_level_steps_name_each_branch(self):
        steps = " ".join(scored(intervention_tested="No", answers_question="No")["level_steps"])
        self.assertIn("Total 11 of 15", steps)
        self.assertIn("caps the level at Moderate", steps)

        harm = scored(study_design="other", equity_level="None", policy_relevance="None", harm_reported="Yes")
        self.assertIn("Override, harm reported: level set to High.", harm["level_steps"])

        skipped = scored(intervention_tested="No", answers_question="No", lmic_setting="No", harm_reported="Yes")
        self.assertIn("Relevance scored 0, so the overrides do not apply.", skipped["level_steps"])

        scope = scored(outcome_touched="NONE")
        self.assertEqual(scope["level_steps"][-1], "Ask the team whether this outcome belongs in the review.")
        self.assertIn("Outcome not covered by the review, so no points",
                      [r["value"] for r in scope["criteria_detail"]])
