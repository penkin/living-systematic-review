import io
import shutil
import tempfile
from pathlib import Path

from django.test import Client, SimpleTestCase, override_settings

GOOD = b'record_id,title,abstract\nSYN-001,Heat and preterm birth,We followed 2340 pregnancies.\n'


class UploadTests(SimpleTestCase):
    def setUp(self):
        self.runs = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.runs)
        self.client = Client()

    def post(self, body, name="cards.csv"):
        with override_settings(RUNS_DIR=self.runs):
            return self.client.post("/", {"cards": io.BytesIO(body)}, follow=True)

    def test_good_csv_creates_a_run_and_lists_the_record(self):
        response = self.post(GOOD)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SYN-001")
        self.assertEqual(len(list(self.runs.iterdir())), 1)

    def test_missing_required_column_is_rejected(self):
        response = self.post(b"record_id,title\nSYN-001,No abstract column\n")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "abstract", status_code=400)
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_header_only_is_rejected(self):
        response = self.post(b"record_id,title,abstract\n")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_unknown_run_is_404(self):
        with override_settings(RUNS_DIR=self.runs):
            response = self.client.get("/run/0198d4f3-0000-4000-8000-000000000000/")
        self.assertEqual(response.status_code, 404)
