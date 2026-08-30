from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.catalogo_landing, name="landing"),
    path("opere/", views.opera_browse, name="browse_all"),
    path("opere/<slug:sezione_slug>/", views.opera_browse, name="browse"),
    path("opera/<str:numero_archivio>/", views.opera_detail, name="detail"),
]
