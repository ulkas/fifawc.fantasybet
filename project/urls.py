from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("", include(("fantasy.urls", "fantasy"), namespace="fantasy")),
    path("admin/", admin.site.urls),
]
