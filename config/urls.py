"""Root URL configuration."""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # API routes
    path("api/v1/", include("route_planner.urls")),

    # OpenAPI schema (raw JSON/YAML)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Swagger UI  →  http://localhost:8000/api/docs/
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    # ReDoc  →  http://localhost:8000/api/redoc/
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
