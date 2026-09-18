import unittest

from pathlib import Path

from signal_tool.evaluate import agreement, equity, hand_levels, hand_tags, parse_handsort, regret, tag_agreement
from signal_tool.test_scoring import REVIEW, RULES

SHEET = (Path(__file__).parent / "testdata" / "handsheet.csv").read_text(encoding="utf-8-sig")


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
        self.assertEqual(parse_handsort("record_id,hand_level\nR1, high\n"), {"R1": {"hand_level": "HIGH"}})
        with self.assertRaises(ValueError):
            parse_handsort("record_id,level\nR1,HIGH\n")
        with self.assertRaises(ValueError):
            parse_handsort("just one column\nR1\n")

    def test_parse_accepts_any_common_delimiter(self):
        two = {"R1": {"hand_level": "HIGH"}, "R2": {"hand_level": "LOW"}}
        for d in (",", ";", "\t", "|"):
            self.assertEqual(parse_handsort(f"record_id{d}hand_level\nR1{d}HIGH\nR2{d}low\n"), two, repr(d))
        sheet = {"R1": {"LMIC?": "Y", "Which outcome 01-09?": "03, 06"}, "R2": {"LMIC?": "N"}}
        self.assertEqual(parse_handsort(',R1,R2\nLMIC?,Y,N\n"Which outcome 01-09?","03, 06",\n'), sheet)
        self.assertEqual(parse_handsort(";R1;R2\r\nLMIC?;Y;N\r\nWhich outcome 01-09?;03, 06;\r\n"), sheet)
        self.assertEqual(parse_handsort("\tR1\tR2\nLMIC?\tY\tN\nWhich outcome 01-09?\t03, 06\t\n"), sheet)

    def test_parse_the_reviewers_sheet(self):
        hand = parse_handsort(SHEET)
        self.assertEqual(len(hand), 34)
        self.assertEqual(hand["SYN-007"]["Which outcome 01-09?"], "03, 06")
        self.assertEqual(hand["SYN-012"], {"Is a finished study": "N"})

    def test_hand_tags_normalise_answers(self):
        tags, unmapped = hand_tags(parse_handsort(SHEET), RULES)
        self.assertEqual(unmapped, ["Not rural?", "Relevant on outcome 01-09?"])
        self.assertEqual(tags["SYN-007"]["outcome_touched"],
                         {"question": "Which outcome 01-09?", "answer": "03, 06", "values": ["O3", "O6"], "label": None})
        self.assertEqual(tags["SYN-001"]["lmic_setting"]["values"], ["Yes"])
        self.assertEqual(tags["SYN-001"]["study_design"]["label"], "Other design")
        self.assertEqual(tags["SYN-003"]["outcome_touched"]["values"], ["NONE"])
        self.assertNotIn("study_design", tags["SYN-031"])
        self.assertNotIn("equity_level", tags["SYN-032"])
        self.assertEqual(tags["SYN-012"], {"lane": {"question": "Is a finished study", "answer": "N", "values": ["separate"], "label": None}})

    def test_parse_the_ranked_file(self):
        text = ("#,Record,Title,SIGNAL,Total,A Rel,Outcome,Review certainty,Override\n"
                "1,R1,Some title,HIGH (override),12,3,7,Very low,HARM\n"
                '2,R2,Other,ROUTE OUT,2,0,"1,8",,NOT A STUDY\n')
        hand = parse_handsort(text)
        self.assertEqual(hand["R1"], {"hand_level": "HIGH (OVERRIDE)", "#": "1", "Title": "Some title", "Total": "12",
                                      "A Rel": "3", "Outcome": "7", "Review certainty": "Very low", "Override": "HARM"})
        tags, unmapped = hand_tags(hand, RULES)
        self.assertEqual(unmapped, ["#", "Title"])
        self.assertEqual(tags["R1"]["signal_score"]["values"], [12])
        self.assertEqual(tags["R1"]["A"]["values"], [3])
        self.assertEqual(tags["R1"]["outcome_certainty"]["values"], ["Very low"])
        self.assertEqual(tags["R1"]["override_triggered"]["values"], ["harm"])
        self.assertEqual(tags["R2"]["outcome_touched"]["values"], ["O1", "O8"])
        self.assertNotIn("override_triggered", tags["R2"])
        levels = hand_levels(ROWS, hand, tags, REVIEW, RULES)
        self.assertEqual((levels["R1"], levels["R2"]), ("HIGH", ""))
        out = tag_agreement([{**ROWS[0], "override_triggered": "harm;absent_context"}, ROWS[1]], tags, RULES)
        self.assertEqual([f["label"] for f in out["fields"]], ["Outcome", "Total", "A Rel", "Review certainty", "Override"])
        self.assertTrue(out["records"][0]["cells"][-1]["agree"])

    def test_tag_agreement_counts_compared_answers_only(self):
        hand = {"R1": {"LMIC?": "Y", "Harm": "N"}, "R3": {"LMIC?": "Y", "Harm": "NA"}, "R9": {"LMIC?": "Y"}}
        tags, _ = hand_tags(hand, RULES)
        out = tag_agreement(ROWS, tags, RULES)
        by_field = {f["field"]: f for f in out["fields"]}
        self.assertEqual((by_field["lmic_setting"]["n"], by_field["lmic_setting"]["agree"]), (2, 1))
        self.assertEqual((by_field["harm_reported"]["n"], by_field["harm_reported"]["agree"]), (1, 1))
        self.assertEqual([r["record_id"] for r in out["records"]], ["R1", "R3"])
        cells = {c["field"]: c for c in out["records"][1]["cells"]}
        self.assertFalse(cells["lmic_setting"]["agree"])
        self.assertIsNone(cells["harm_reported"]["agree"])

    def test_hand_levels_score_the_answers_with_the_rubric(self):
        hand = {"R1": {"Is a finished study": "N"}, "R2": {"hand_level": "LOW"}, "R3": {"LMIC?": "Y", "Harm": "Y"}, "R4": {"Is a finished study": "Y"}}
        tags, _ = hand_tags(hand, RULES)
        levels = hand_levels(ROWS, hand, tags, REVIEW, RULES)
        self.assertEqual(levels["R1"], "")
        self.assertEqual(levels["R2"], "LOW")
        # R3 scores LOW with the tool's tags; the reviewers' setting and harm answers raise the level.
        self.assertEqual(levels["R3"], "HIGH")
        self.assertIn(levels["R4"], ("LOW", "MODERATE", "HIGH"))
        self.assertNotIn("R5", hand_levels(ROWS, {"R5": {"Not rural?": "Y"}}, hand_tags({"R5": {"Not rural?": "Y"}}, RULES)[0], REVIEW, RULES))

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
