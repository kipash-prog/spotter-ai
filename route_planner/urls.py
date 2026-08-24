"""URL routing for the route_planner app."""

from django.urls import path
from route_planner.views import RoutePlannerView

app_name = "route_planner"

urlpatterns = [
    path("route/", RoutePlannerView.as_view(), name="route"),
]
