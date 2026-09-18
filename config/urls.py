from django.urls import path

from web import views

urlpatterns = [
    path("", views.run_list, name="run_list"),
    path("new/", views.upload, name="upload"),
    path("run/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("run/<uuid:run_id>/record/<str:record_id>/", views.record_detail, name="record_detail"),
    path("run/<uuid:run_id>/record/<str:record_id>/tag/", views.set_tag, name="set_tag"),
    path("run/<uuid:run_id>/signals.csv", views.signals_csv, name="signals_csv"),
    path("run/<uuid:run_id>/evaluate/", views.evaluate, name="evaluate"),
    path("run/<uuid:run_id>/rubric.yaml", views.run_settings, {"name": "rubric"}, name="run_rubric"),
    path("run/<uuid:run_id>/review.yaml", views.run_settings, {"name": "review"}, name="run_review"),
    path("rubrics/", views.rubric_list, name="rubric_list"),
    path("rubrics/new/", views.rubric_new, name="rubric_new"),
    path("rubrics/<uuid:rubric_id>/", views.rubric_edit, name="rubric_edit"),
    path("rubrics/<uuid:rubric_id>/copy/", views.rubric_copy, name="rubric_copy"),
    path("rubrics/<uuid:rubric_id>/prompt/", views.rubric_prompt, name="rubric_prompt"),
]
