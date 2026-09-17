import csv
import io
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase, override_settings

GOOD = b'record_id,title,abstract\nSYN-001,Heat and preterm birth,We followed 2340 pregnancies.\n'


def cache_files():
    return sorted(p.name for p in settings.MODEL_CACHE.iterdir())


class UploadTests(SimpleTestCase):
    def setUp(self):
        self.runs = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.runs)
        self.client = Client()

    def post(self, body):
        with override_settings(RUNS_DIR=self.runs):
            return self.client.post("/", {"cards": io.BytesIO(body)}, follow=True)

    def test_good_csv_creates_a_run_and_lists_the_record(self):
        response = self.post(GOOD)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SYN-001")
        # This title is not in the committed cache, so the record stays listed but unscored.
        self.assertContains(response, "Not ranked")
        self.assertEqual(len(list(self.runs.iterdir())), 1)
        with override_settings(RUNS_DIR=self.runs):
            detail = self.client.get(response.request["PATH_INFO"] + "record/SYN-001/")
        self.assertContains(detail, "no response for this record yet")
        self.assertContains(detail, "Not ranked")
        self.assertNotContains(detail, "How the score was built")

    def test_missing_required_column_is_rejected(self):
        response = self.post(b"record_id,title\nSYN-001,No abstract column\n")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "abstract", status_code=400)
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_header_only_is_rejected(self):
        response = self.post(b"record_id,title,abstract\n")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_retracted_record_is_shown_in_the_separate_lane(self):
        response = self.post(
            GOOD + b"SYN-012,RETRACTED: Stroke admissions in Lagos,RETRACTED ARTICLE. Withdrawn.\n"
        )
        self.assertContains(response, "1 ranked, 1 set aside")
        self.assertContains(response, "Retracted by the publisher")

    def test_unknown_run_is_404(self):
        with override_settings(RUNS_DIR=self.runs):
            response = self.client.get("/run/0198d4f3-0000-4000-8000-000000000000/")
        self.assertEqual(response.status_code, 404)


class RunTests(SimpleTestCase):
    """The full cards.csv, scored from the committed cache and never from a model."""

    def setUp(self):
        self.runs = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.runs)
        self.settings = override_settings(RUNS_DIR=self.runs)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.client = Client()
        with (settings.BASE_DIR / "cards.csv").open("rb") as handle:
            response = self.client.post("/", {"cards": handle})
        self.run_url = response["Location"]
        self.run_id = self.run_url.rstrip("/").rsplit("/", 1)[1]

    def signals(self):
        text = (self.runs / self.run_id / "signals.csv").read_text(encoding="utf-8")
        return {row["record_id"]: row for row in csv.DictReader(io.StringIO(text))}

    def test_dashboard_ranks_and_keeps_every_record(self):
        response = self.client.get(self.run_url)
        self.assertContains(response, "29 ranked, 5 set aside")
        for i in range(1, 35):
            self.assertContains(response, f'id="SYN-{i:03d}"')
        body = response.content.decode()
        self.assertLess(body.index('id="SYN-022"'), body.index('id="SYN-003"'), "HIGH sorts before MODERATE")
        self.assertContains(response, "Override: harm reported")
        self.assertContains(response, "Ask the team whether this outcome belongs in the review.")
        self.assertContains(response, "/record/SYN-022/")
        self.assertContains(response, "What the review already knows")
        self.assertContains(response, "Effectiveness of cooling interventions")
        self.assertContains(response, "Childhood diarrhoeal disease")

    def test_record_detail_page(self):
        page = self.client.get(f"{self.run_url}record/SYN-022/")
        self.assertContains(page, "How the score was built")
        self.assertContains(page, "How the level was set")
        self.assertContains(page, "Relevance to the review question")
        self.assertContains(page, "One point each for testing an intervention")
        self.assertContains(page, "Tagged by anthropic/")
        self.assertContains(page, "Suggested")
        self.assertContains(page, "Agree")
        self.assertContains(page, "harm reported")

        aside = self.client.get(f"{self.run_url}record/SYN-031/")
        self.assertContains(aside, "Set aside")
        self.assertNotContains(aside, "How the score was built")

        self.assertEqual(self.client.get(f"{self.run_url}record/SYN-999/").status_code, 404)

    def test_override_rescores_without_a_model_call(self):
        before = cache_files()
        run_model = self.runs / self.run_id / "model"
        model_before = sorted(p.name for p in run_model.iterdir())
        self.assertEqual(self.signals()["SYN-003"]["signal_level"], "MODERATE")

        response = self.client.post(
            f"{self.run_url}record/SYN-003/tag/", {"field": "harm_reported", "value": "Yes"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("/record/SYN-003/#tag-harm_reported"))
        row = self.signals()["SYN-003"]
        self.assertEqual(row["signal_level"], "HIGH")
        self.assertEqual(row["override_triggered"], "harm")
        self.assertEqual(cache_files(), before)
        self.assertEqual(sorted(p.name for p in run_model.iterdir()), model_before)

        page = self.client.get(response["Location"])
        self.assertContains(page, "Changed")
        self.assertContains(page, "Override, harm reported: level set to High.")

    def test_confirm_keeps_the_value_and_marks_it_confirmed(self):
        response = self.client.post(f"{self.run_url}record/SYN-003/tag/", {"field": "harm_reported", "value": "No"})
        page = self.client.get(response["Location"])
        self.assertContains(page, "Agreed")
        # Four tags still wait for a look; the agreed one has no controls left.
        self.assertEqual(page.content.decode().count(">Agree</button>"), 4)
        self.assertEqual(page.content.decode().count(">Change</button>"), 4)
        self.assertEqual(self.signals()["SYN-003"]["signal_level"], "MODERATE")

    def test_record_type_override_moves_a_record_into_scoring(self):
        self.client.post(
            f"{self.run_url}record/SYN-031/tag/", {"field": "record_type", "value": "journal_article"}
        )
        row = self.signals()["SYN-031"]
        self.assertEqual(row["lane"], "signal")
        self.assertIn(row["signal_level"], ("LOW", "MODERATE", "HIGH"))

    def test_bad_tag_requests_are_400(self):
        base = f"{self.run_url}record/SYN-003/tag/"
        self.assertEqual(self.client.post(base, {"field": "study_design", "value": "RCT"}).status_code, 400)
        self.assertEqual(self.client.post(base, {"field": "harm_reported", "value": "Maybe"}).status_code, 400)
        self.assertEqual(
            self.client.post(f"{self.run_url}record/SYN-999/tag/", {"field": "harm_reported", "value": "Yes"}).status_code,
            400,
        )

    def test_csv_download(self):
        response = self.client.get(f"{self.run_url}signals.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("signals.csv", response["Content-Disposition"])
        text = b"".join(response.streaming_content).decode("utf-8")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(text)))), 34)

    def test_evaluate_page_and_hand_sort(self):
        page = self.client.get(f"{self.run_url}evaluate/")
        self.assertContains(page, "Fairness check")
        self.assertContains(page, "Low- or middle-income setting")
        self.assertNotContains(page, "Record by record")

        bad = self.client.post(f"{self.run_url}evaluate/", {"handsort": io.BytesIO(b"record_id,level\nSYN-001,HIGH\n")})
        self.assertEqual(bad.status_code, 400)

        handsort = b"record_id,hand_level\nSYN-001,HIGH\nSYN-003,LOW\nSYN-013,HIGH\nSYN-031,HIGH\n"
        response = self.client.post(f"{self.run_url}evaluate/", {"handsort": io.BytesIO(handsort)}, follow=True)
        self.assertContains(response, "Record by record")
        self.assertContains(response, "outside its top")
        self.assertContains(response, 'class="bg-base-200"')
        # SYN-031 is separate lane, so it has no rank and is a regret miss.
        self.assertContains(response, "Not ranked")
