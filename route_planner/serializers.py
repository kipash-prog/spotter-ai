"""
DRF serializers for the route planner API.
"""

from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Validates incoming route request payload."""

    start = serializers.CharField(
        max_length=500,
        help_text="Start location — US city/address or 'lat,lon' coordinates",
    )
    finish = serializers.CharField(
        max_length=500,
        help_text="Finish location — US city/address or 'lat,lon' coordinates",
    )

    def validate_start(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("start location cannot be empty.")
        return value

    def validate_finish(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("finish location cannot be empty.")
        return value

    def validate(self, data):
        if data.get("start", "").lower() == data.get("finish", "").lower():
            raise serializers.ValidationError(
                "start and finish locations must be different."
            )
        return data


class FuelStopSerializer(serializers.Serializer):
    """A single recommended fuel stop."""

    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    distance_from_start_miles = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    cost_at_this_stop = serializers.FloatField()


class RouteInfoSerializer(serializers.Serializer):
    """High-level route metadata."""

    start = serializers.CharField()
    finish = serializers.CharField()
    start_lat = serializers.FloatField()
    start_lon = serializers.FloatField()
    finish_lat = serializers.FloatField()
    finish_lon = serializers.FloatField()
    total_distance_miles = serializers.FloatField()
    estimated_duration_hours = serializers.FloatField()
    route_geometry = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        help_text="List of [lon, lat] coordinate pairs forming the route polyline",
    )
    map_url = serializers.URLField(allow_blank=True)


class RouteResponseSerializer(serializers.Serializer):
    """Full API response."""

    route = RouteInfoSerializer()
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_cost = serializers.FloatField()
    total_gallons = serializers.FloatField()
    vehicle_range_miles = serializers.IntegerField()
    vehicle_mpg = serializers.IntegerField()
