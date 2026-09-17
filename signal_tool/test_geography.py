import unittest
from pathlib import Path

from signal_tool.geography import countries_in_text, load_reference, resolve
from signal_tool.tagging import load_rules

ROOT = Path(__file__).resolve().parents[1]
REF = load_reference(ROOT / "reference")
RULES = load_rules(str(ROOT / "rubric.yaml"))


class CountryMatchTests(unittest.TestCase):
    def test_exact_name_matches_case_insensitively(self):
        self.assertEqual(countries_in_text("A trial in SOUTH AFRICA and Ghana.", REF), ["GHA", "ZAF"])

    def test_a_name_inside_a_word_does_not_match(self):
        self.assertEqual(countries_in_text("Indiana and Nigerians", REF), [])

    def test_the_iso_long_form_does_not_match_the_short_form(self):
        # Expected: stage 2 supplies TZA. SPEC.md section 5 forbids fuzzy matching.
        self.assertEqual(countries_in_text("Dar es Salaam, Tanzania", REF), [])


class ResolveTests(unittest.TestCase):
    def test_western_africa_comes_from_the_intermediate_column(self):
        geo = resolve(["BFA"], REF, RULES)
        self.assertIn("Western Africa", geo["regions"])
        self.assertIn("Africa", geo["regions"])
        self.assertEqual(geo["lmic_setting"], "Yes")

    def test_a_high_income_country_is_not_lmic(self):
        self.assertEqual(resolve(["GBR"], REF, RULES)["lmic_setting"], "No")

    def test_mixed_settings(self):
        self.assertEqual(resolve(["GBR", "GHA"], REF, RULES)["lmic_setting"], "Mixed")

    def test_no_country_is_unclear(self):
        geo = resolve([], REF, RULES)
        self.assertEqual(geo["lmic_setting"], "Unclear")
        self.assertEqual(geo["regions"], [])

    def test_unknown_codes_are_dropped(self):
        self.assertEqual(resolve(["XXX"], REF, RULES)["countries"], [])

    def test_reference_carries_a_download_date(self):
        self.assertRegex(REF["date"], r"^\d{4}-\d{2}-\d{2}$")
