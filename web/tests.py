import base64
import collections
import csv
import io
import re
from html.parser import HTMLParser
from unittest.mock import patch

import yaml
from django.conf import settings
from django.test import Client, TestCase, override_settings

from signal_tool import pipeline
from signal_tool.suggest import MODEL
from signal_tool.test_suggest import FixtureClient
from web.models import Record, Result, Rubric, Run, Tag
from web.tasks import config, process_run

# SYN-901 has no fixture, so the fixture client raises and the record stays listed but unscored.
GOOD = b'record_id,title,abstract\nSYN-901,Heat and preterm birth,We followed 2340 pregnancies.\n'


def failing_client(system, user, schema):
    raise RuntimeError("model down")


class WebTestCase(TestCase):
    """Uploads are tagged inline from the fixtures: the in-memory test database is not shared across threads."""

    def setUp(self):
        self.model = FixtureClient()
        self.enterContext(patch("web.views.start_run", new=process_run))
        self.enterContext(patch("web.views.build_client", return_value=self.model))
        self.client = Client()

    def post(self, body):
        return self.client.post("/new/", {"cards": io.BytesIO(body)}, follow=True)


class UploadTests(WebTestCase):
    def test_good_csv_creates_a_run_and_lists_the_record(self):
        response = self.post(GOOD)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SYN-901")
        self.assertContains(response, "Not ranked")
        self.assertEqual(Run.objects.count(), 1)
        detail = self.client.get(response.request["PATH_INFO"] + "record/SYN-901/")
        self.assertContains(detail, "no response for this record")
        self.assertContains(detail, "Not ranked")
        self.assertNotContains(detail, "How the score was built")

    def test_missing_required_column_is_rejected(self):
        response = self.post(b"record_id,title\nSYN-901,No abstract column\n")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "abstract", status_code=400)
        self.assertEqual(Run.objects.count(), 0)

    def test_header_only_is_rejected(self):
        response = self.post(b"record_id,title,abstract\n")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Run.objects.count(), 0)

    def test_repeated_record_id_is_rejected(self):
        response = self.post(GOOD + GOOD.splitlines()[1] + b"\n")
        self.assertContains(response, "Repeated record_id: SYN-901", status_code=400)
        self.assertEqual(Run.objects.count(), 0)

    def test_no_api_key_is_rejected_before_a_run_exists(self):
        with patch("web.views.build_client", return_value=None):
            response = self.post(GOOD)
        self.assertContains(response, "OPENROUTER_API_KEY", status_code=400)
        self.assertEqual(Run.objects.count(), 0)

    def test_retracted_record_is_shown_in_the_separate_lane(self):
        response = self.post(
            GOOD + b"SYN-012,RETRACTED: Stroke admissions in Lagos,RETRACTED ARTICLE. Withdrawn.\n"
        )
        self.assertContains(response, "1 ranked")
        self.assertContains(response, '<div class="stat-title">Set aside</div>\n    <div class="stat-value">1</div>', html=False)
        self.assertContains(response, "Retracted by the publisher")

    def test_failed_model_call_is_shown_on_the_record(self):
        with patch("web.views.build_client", return_value=failing_client):
            response = self.post(GOOD)
        self.assertContains(response, "Not ranked")
        self.assertEqual(Run.objects.get().status, Run.DONE)
        detail = self.client.get(response.request["PATH_INFO"] + "record/SYN-901/")
        self.assertContains(detail, "The model call failed")
        self.assertContains(detail, "RuntimeError: model down")

    def test_run_page_polls_while_tagging(self):
        run = Run.objects.create()
        first = Record.objects.create(run=run, record_id="A", title="Done one")
        Record.objects.create(run=run, record_id="B", title="Waiting one")
        Result.objects.create(record=first, signal_level="LOW", signal_score=3,
                              detail={"record_id": "A", "title": "Done one", "lane": "signal", "signal_level": "LOW",
                                      "signal_score": 3, "signal_max": 15, "signal_reason": "Low.", "suggested_action": "Note"})
        page = self.client.get(f"/run/{run.pk}/")
        self.assertContains(page, '" data-poll>')
        self.assertContains(page, "Tagged 1 of 2 records")
        self.assertContains(page, "loading-spinner")
        self.assertContains(page, "Tagging this record.")
        body = page.content.decode()
        self.assertLess(body.index('id="A"'), body.index('id="B"'), "a tagged row sorts above a waiting one")

        detail = self.client.get(f"/run/{run.pk}/record/B/")
        self.assertContains(detail, '" data-poll>')
        self.assertContains(detail, "Tagging this record")

        run.status, run.error = Run.FAILED, "RuntimeError: boom"
        run.save()
        page = self.client.get(f"/run/{run.pk}/")
        self.assertNotContains(page, '" data-poll>')
        self.assertContains(page, "Tagging stopped: RuntimeError: boom")

    def test_unknown_run_is_404(self):
        response = self.client.get("/run/0198d4f3-0000-4000-8000-000000000000/")
        self.assertEqual(response.status_code, 404)


class RunTests(WebTestCase):
    """The full cards.csv, tagged from the fixture responses."""

    def setUp(self):
        super().setUp()
        with (settings.BASE_DIR / "cards.csv").open("rb") as handle:
            response = self.client.post("/new/", {"cards": handle})
        self.run_url = response["Location"]
        self.run_id = self.run_url.rstrip("/").rsplit("/", 1)[1]

    def signals(self):
        text = self.client.get(f"{self.run_url}signals.csv").content.decode("utf-8")
        return {row["record_id"]: row for row in csv.DictReader(io.StringIO(text))}

    def test_dashboard_ranks_and_keeps_every_record(self):
        response = self.client.get(self.run_url)
        self.assertContains(response, "29 ranked")
        self.assertContains(response, '<div class="stat-title">Set aside</div>\n    <div class="stat-value">5</div>')
        self.assertContains(response, 'High</span></div>\n    <div class="stat-value">13</div>')
        self.assertNotContains(response, '" data-poll>')
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
        self.assertContains(page, f"Tagged by {MODEL}")
        self.assertContains(page, "Suggested")
        self.assertContains(page, "Agree")
        self.assertContains(page, "harm reported")

        aside = self.client.get(f"{self.run_url}record/SYN-031/")
        self.assertContains(aside, "Set aside")
        self.assertNotContains(aside, "How the score was built")

        self.assertEqual(self.client.get(f"{self.run_url}record/SYN-999/").status_code, 404)

    def test_override_rescores_without_a_model_call(self):
        record = Record.objects.get(run_id=self.run_id, record_id="SYN-003")
        stored = record.model_response
        self.assertEqual(self.model.calls, 34)
        self.assertEqual(self.signals()["SYN-003"]["signal_level"], "MODERATE")

        response = self.client.post(
            f"{self.run_url}record/SYN-003/tag/", {"field": "harm_reported", "value": "Yes"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("/record/SYN-003/#tag-harm_reported"))
        row = self.signals()["SYN-003"]
        self.assertEqual(row["signal_level"], "HIGH")
        self.assertEqual(row["override_triggered"], "harm")
        self.assertEqual(self.model.calls, 34)
        record.refresh_from_db()
        self.assertEqual(record.model_response, stored)

        page = self.client.get(response["Location"])
        self.assertContains(page, "Changed")
        self.assertContains(page, "Override, harm reported: level set to High.")

    def test_confirm_keeps_the_value_and_marks_it_confirmed(self):
        response = self.client.post(f"{self.run_url}record/SYN-003/tag/", {"field": "harm_reported", "value": "No"})
        page = self.client.get(response["Location"])
        self.assertContains(page, "Agreed")
        # Four tags still wait for a look; the agreed one keeps only its Change control.
        self.assertEqual(page.content.decode().count(">Agree</button>"), 4)
        self.assertEqual(page.content.decode().count(">Change</button>"), 5)
        self.assertEqual(self.signals()["SYN-003"]["signal_level"], "MODERATE")

    def test_a_reviewer_can_change_a_tag_after_agreeing(self):
        base = f"{self.run_url}record/SYN-003/tag/"
        self.client.post(base, {"field": "harm_reported", "value": "No"})
        self.client.post(base, {"field": "harm_reported", "value": "Yes"})
        self.assertEqual(self.signals()["SYN-003"]["signal_level"], "HIGH")
        self.client.post(base, {"field": "harm_reported", "value": "No"})
        self.assertEqual(self.signals()["SYN-003"]["signal_level"], "MODERATE")
        relevance = Tag.objects.get(record__run_id=self.run_id, record__record_id="SYN-003", field="relevance").value
        self.client.post(base, {"field": "relevance", "value": relevance})
        page = self.client.get(self.run_url)
        self.assertContains(page, "Checked by a reviewer")
        self.assertContains(page, "✓ 1")
        self.assertContains(page, "✎ 1")

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
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))
        self.assertEqual(len(rows), 34)
        self.assertEqual(list(rows[0]), list(pipeline.COLUMNS))

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
        self.assertNotContains(response, "Question by question")

    def test_evaluate_page_reads_the_reviewers_sheet(self):
        sheet = open(settings.BASE_DIR / "signal_tool" / "testdata" / "handsheet.csv", "rb").read()
        response = self.client.post(f"{self.run_url}evaluate/", {"handsort": io.BytesIO(sheet)}, follow=True)
        self.assertContains(response, "Question by question")
        self.assertContains(response, "Not rural?")
        self.assertNotContains(response, "You: 03, 06")
        self.assertContains(response, "You: O3 ")
        self.assertContains(response, " or O6 ")
        self.assertContains(response, "You: Low- or middle-income")
        self.assertContains(response, "You: Other design")
        self.assertContains(response, "scored with the same rubric")
        self.assertNotContains(response, "Not in this run")

    def test_evaluate_page_reads_the_ranked_file(self):
        ranked = (b"#,Record,Title,SIGNAL,Total,A Rel,B LMIC,Outcome,Review certainty,Override\n"
                  b"1,SYN-001,Nairobi,HIGH (override),12,3,2,5,Very low,HARM\n"
                  b"2,SYN-031,Lusaka,ROUTE OUT,2,0,0,,,NOT A STUDY\n")
        response = self.client.post(f"{self.run_url}evaluate/", {"handsort": io.BytesIO(ranked)}, follow=True)
        self.assertContains(response, "Question by question")
        self.assertContains(response, "Relevance to the review question")
        self.assertContains(response, "You: Very low")
        self.assertContains(response, "You: harm reported")
        self.assertNotContains(response, "harm;")
        self.assertContains(response, "Not compared, the tool has no tag for these: #, Title.")
        self.assertNotContains(response, "Which outcome 01-09?")

    def test_record_page_explains_the_lmic_setting(self):
        page = self.client.get(f"{self.run_url}record/SYN-001/")
        self.assertContains(page, "Kenya: Lower-middle income, from the text and the model")
        self.assertContains(page, "Groups that count: Low income, Lower-middle income, Upper-middle income")
        page = self.client.get(f"{self.run_url}record/SYN-027/")
        self.assertContains(page, "No country found in the title, abstract or location")


class PasswordGateTests(TestCase):
    @staticmethod
    def basic(password):
        return "Basic " + base64.b64encode(f"anyone:{password}".encode()).decode()

    @override_settings(APP_PASSWORD="secret")
    def test_the_browser_is_asked_for_the_password(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic", response["WWW-Authenticate"])
        self.assertEqual(self.client.get("/", HTTP_AUTHORIZATION=self.basic("wrong")).status_code, 401)
        self.assertEqual(self.client.get("/", HTTP_AUTHORIZATION="Basic not-base64").status_code, 401)
        self.assertEqual(self.client.get("/", HTTP_AUTHORIZATION=self.basic("secret")).status_code, 200)

    @override_settings(APP_PASSWORD="")
    def test_no_password_means_no_gate(self):
        self.assertEqual(self.client.get("/").status_code, 200)


class RunListTests(WebTestCase):
    def rank(self):
        with (settings.BASE_DIR / "cards.csv").open("rb") as handle:
            response = self.client.post("/new/", {"cards": handle})
        return Run.objects.get(pk=response["Location"].rstrip("/").rsplit("/", 1)[1])

    def test_empty_settings_fall_back_to_the_files(self):
        run = Run.objects.create(filename="old.csv")
        self.assertEqual(config(run)[:2], config()[:2])
        self.assertEqual(self.client.get(f"/run/{run.pk}/rubric.yaml").content.decode(), settings.RUBRIC_CONFIG.read_text())

    def test_run_list_shows_every_run_with_its_counts(self):
        first = self.rank()
        second = self.rank()
        page = self.client.get("/")
        self.assertContains(page, f'href="/run/{first.pk}/"')
        self.assertContains(page, f'href="/run/{second.pk}/"')
        self.assertEqual(self.counts(page, first), ["34", "13", "10", "6", "0", "5"])
        self.assertContains(page, "v0 · ")
        self.assertContains(page, 'href="/new/"')
        self.assertContains(self.client.get(f"/run/{first.pk}/rubric.yaml"), "rubric_version: v0")

    @staticmethod
    def counts(page, run):
        """The number cells of one row of the run list: records, one per level, checked, set aside."""
        html = page.content.decode()
        row = html[html.index(f'id="run-{run.pk}"') :].split("</tr>", 1)[0]
        return re.findall(r'<td class="text-center">(\d+)</td>', row)


class FormParser(HTMLParser):
    """The inputs, selects and textareas of a page as the browser posts them, with the <template> rows left out."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data = collections.defaultdict(list)
        self.templates = 0
        self.select = self.textarea = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "template":
            self.templates += 1
        if self.templates or not a.get("name", tag == "option"):
            return
        if tag == "input":
            kind = a.get("type", "text")
            if kind in ("submit", "button", "file") or (kind in ("checkbox", "radio") and "checked" not in a):
                return
            self.data[a["name"]].append(a.get("value") or "")
        elif tag == "select":
            self.select = (a["name"], "multiple" in a, [], [])
        elif tag == "option" and self.select:
            self.select[2].append(a.get("value", ""))
            if "selected" in a:
                self.select[3].append(a.get("value", ""))
        elif tag == "textarea":
            self.textarea = a["name"]
            self.data[a["name"]].append("")

    def handle_endtag(self, tag):
        if tag == "template":
            self.templates -= 1
        elif tag == "select" and self.select:
            name, multiple, options, selected = self.select
            self.data[name].extend(selected or ([] if multiple else options[:1]))
            self.select = None
        elif tag == "textarea":
            self.textarea = None

    def handle_data(self, data):
        if self.textarea and not self.templates:
            self.data[self.textarea][-1] += data


class RubricTests(TestCase):
    def new(self):
        response = self.client.post("/rubrics/new/", follow=True)
        return Rubric.objects.get(), response

    @staticmethod
    def form(response):
        parser = FormParser()
        parser.feed(response.content.decode())
        return parser.data

    def save(self, rubric, data):
        response = self.client.post(f"/rubrics/{rubric.pk}/", data, follow=True)
        rubric.refresh_from_db()
        return response, yaml.safe_load(rubric.rubric_yaml), yaml.safe_load(rubric.review_yaml)

    def test_a_new_rubric_holds_the_files(self):
        rubric, response = self.new()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New rubric")
        review, rules, _ = config()
        self.assertEqual(yaml.safe_load(rubric.rubric_yaml), rules)
        self.assertEqual(yaml.safe_load(rubric.review_yaml), review)

    def test_saving_the_form_unchanged_builds_the_same_rubric(self):
        rubric, response = self.new()
        response, rules, review = self.save(rubric, self.form(response))
        self.assertContains(response, "Saved.")
        file_review, file_rules, _ = config()
        self.assertEqual(rules, file_rules)
        # The file ends the question with a newline; the form box strips it.
        file_review["review_question"] = file_review["review_question"].strip()
        self.assertEqual(review, file_review)

    def test_a_rubric_for_another_review(self):
        rubric, response = self.new()
        data = self.form(response)
        data["rubric_name"] = ["Cost review"]
        data["crit_id"][data["crit_id"].index("D")] = ""
        for column, value in zip(("id", "label", "values", "prompt", "confirmable", "type"), ("cost_reported", "Cost reported", "Yes, No", "Yes if the record reports a cost.", "yes", "")):
            data[f"field_{column}"].append(value)
        for column, value in zip(("index", "id", "name", "help", "max", "default"), ("9", "H", "Cost", "One point when a cost is reported.", "1", "0")):
            data[f"crit_{column}"].append(value)
        data.update(score_9_field=["cost_reported"], score_9_value=["Yes"], score_9_points=["1"])
        data.update(override_name=["cost"], override_label=[""], override_field=["cost_reported"], override_equals=["Yes"], override_action=["raise"])
        response, rules, review = self.save(rubric, data)
        self.assertContains(response, "Saved.")
        self.assertContains(response, '<option value="cost_reported" selected>')
        self.assertContains(response, "- cost_reported: Yes if the record reports a cost.")
        self.assertContains(response, "&quot;cost_reported&quot;: {")
        self.assertEqual(rubric.name, "Cost review")
        self.assertNotIn("D", rules["criteria"])
        self.assertEqual(
            rules["criteria"]["H"],
            {"name": "Cost", "help": "One point when a cost is reported.", "max": 1, "source_field": "cost_reported", "default": 0, "scores": {"Yes": 1}},
        )
        self.assertEqual(rules["overrides"], [{"name": "cost", "label": "cost", "source_field": "cost_reported", "equals": "Yes", "action": "raise"}])
        self.assertEqual(
            rules["fields"][-1],
            {"id": "cost_reported", "source": "model", "label": "Cost reported", "values": ["Yes", "No"], "prompt": "Yes if the record reports a cost.", "confirmable": True},
        )
        self.assertEqual(rules["criteria"]["A"]["parts"][0]["scores"], {"Yes": 1})
        self.assertEqual(rules["criteria"]["F"]["scores"], {1: 1})

    def test_a_bad_row_shows_the_error_and_keeps_the_rubric(self):
        rubric, response = self.new()
        data = self.form(response)
        data["override_field"][0] = "nothing"
        response = self.client.post(f"/rubrics/{rubric.pk}/", data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "not in the list: nothing", status_code=400)
        data = self.form(self.client.get(f"/rubrics/{rubric.pk}/"))
        del data["score_2_field"], data["score_2_value"], data["score_2_points"]
        response = self.client.post(f"/rubrics/{rubric.pk}/", data)
        self.assertContains(response, "needs at least one scored value", status_code=400)
        self.assertEqual(yaml.safe_load(rubric.rubric_yaml), config()[1])

    def test_the_list_shows_every_rubric_and_copies_one(self):
        rubric, _ = self.new()
        self.client.post(f"/rubrics/{rubric.pk}/copy/", follow=True)
        page = self.client.get("/rubrics/")
        self.assertContains(page, "Copy of New rubric")
        self.assertEqual(Rubric.objects.count(), 2)
        self.assertContains(self.client.get("/"), 'href="/rubrics/"')
