from django.urls import path

from web import views

urlpatterns = [
    path("", views.upload, name="upload"),
    path("run/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("run/<uuid:run_id>/record/<str:record_id>/", views.record_detail, name="record_detail"),
    path("run/<uuid:run_id>/record/<str:record_id>/tag/", views.set_tag, name="set_tag"),
    path("run/<uuid:run_id>/signals.csv", views.signals_csv, name="signals_csv"),
    path("run/<uuid:run_id>/evaluate/", views.evaluate, name="evaluate"),
]
