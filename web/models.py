import uuid

from django.db import models


class Run(models.Model):
    PROCESSING, DONE, FAILED = "processing", "done", "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    filename = models.TextField(blank=True)
    status = models.TextField(default=PROCESSING)
    error = models.TextField(blank=True)
    handsort = models.TextField(blank=True)
    # The rules the run was tagged and scored with, as YAML text. Empty means the files on disk,
    # which is what every run made before these columns existed used.
    rubric_yaml = models.TextField(blank=True)
    review_yaml = models.TextField(blank=True)
    # Which saved rubric the text above was copied from. Null for a run made before rubrics existed.
    rubric = models.ForeignKey("Rubric", null=True, blank=True, on_delete=models.SET_NULL, related_name="runs")


class Rubric(models.Model):
    """A set of rules and a review built in the rubric builder. The same two YAML texts a Run stores."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    rubric_yaml = models.TextField()
    review_yaml = models.TextField()

    class Meta:
        ordering = ["-updated"]


class Record(models.Model):
    INPUT_FIELDS = ("record_id", "title", "abstract", "record_type_raw", "year", "language", "location")

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="records")
    record_id = models.TextField()
    title = models.TextField(blank=True)
    abstract = models.TextField(blank=True)
    record_type_raw = models.TextField(blank=True)
    year = models.TextField(blank=True)
    language = models.TextField(blank=True)
    location = models.TextField(blank=True)
    # The validated stage 2 response. A confirmation re-scores from this, so it never repeats the model call.
    model_response = models.JSONField(null=True, blank=True)
    model_status = models.TextField(default="pending")
    model_error = models.TextField(blank=True)

    class Meta:
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["run", "record_id"], name="record_unique_per_run")]

    def as_dict(self):
        return {field: getattr(self, field) for field in self.INPUT_FIELDS}


class Tag(models.Model):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="tags")
    field = models.TextField()
    value = models.JSONField(null=True, blank=True)
    status = models.TextField()
    evidence = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["record", "field"], name="tag_unique_per_record")]


class Result(models.Model):
    record = models.OneToOneField(Record, on_delete=models.CASCADE, related_name="result")
    signal_level = models.TextField(blank=True)
    signal_score = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict)
