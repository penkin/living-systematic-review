from django.urls import path

from web import views

urlpatterns = [
    path("", views.upload, name="upload"),
    path("run/<uuid:run_id>/", views.run_detail, name="run_detail"),
]
