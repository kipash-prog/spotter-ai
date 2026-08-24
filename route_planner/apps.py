"""
AppConfig for route_planner.

Loads and indexes the fuel station dataset at startup so that
every subsequent request can perform sub-millisecond spatial lookups
without touching the filesystem or database.
"""

from django.apps import AppConfig


class RoutePlannerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "route_planner"

    def ready(self):
        # Import here to avoid circular imports and ensure Django is fully loaded
        from route_planner.services.fuel_loader import FuelStationIndex
        FuelStationIndex.load()
