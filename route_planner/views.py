"""
Route Planner API Views.

POST /api/v1/route/
    Body: { "start": "...", "finish": "..." }
    Returns: full route info + optimal fuel stops + total cost
"""

import logging
import time

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from route_planner.serializers import RouteRequestSerializer, RouteResponseSerializer
from route_planner.services.geocoder import geocode, GeocoderError
from route_planner.services.router import get_route, RouterError, build_map_url
from route_planner.services.fuel_loader import FuelStationIndex
from route_planner.services.fuel_optimizer import (
    assign_mileposts,
    find_optimal_stops,
    _cumulative_distances,
)

logger = logging.getLogger(__name__)


class RoutePlannerView(APIView):
    """
    Compute an optimal fuel-stop plan for a US road trip.

    **Request (POST)**
    ```json
    {
        "start": "New York, NY",
        "finish": "Los Angeles, CA"
    }
    ```

    **Response**
    ```json
    {
        "route": { ... },
        "fuel_stops": [ ... ],
        "total_fuel_cost": 987.65,
        "total_gallons": 279.85,
        "vehicle_range_miles": 500,
        "vehicle_mpg": 10
    }
    ```

    **API calls made:**
    - Up to 2 calls to ORS /geocode/search (skipped if raw coords are provided)
    - Exactly 1 call to ORS /v2/directions (cached on subsequent requests)
    """

    @extend_schema(
        tags=["Route Planning"],
        summary="Plan optimal fuel stops for a US road trip",
        description=(
            "Given a start and finish location within the USA, returns the full driving route "
            "along with the most cost-effective fuel stops based on current retail prices. "
            "\n\n"
            "**Vehicle assumptions:** 500-mile max range, 10 mpg fuel economy."
            "\n\n"
            "**External API calls per request:**\n"
            "- Up to 2 × ORS geocoding (skipped if raw `lat,lon` coordinates are supplied)\n"
            "- Exactly 1 × ORS routing (result cached for 1 hour)\n"
            "\n\n"
            "**Fuel stop algorithm:** Greedy cost-minimization — buys just enough fuel "
            "to reach a cheaper station ahead; fills completely when none exists."
        ),
        request=RouteRequestSerializer,
        responses={
            200: RouteResponseSerializer,
            400: OpenApiResponse(description="Missing or invalid input fields"),
            422: OpenApiResponse(description="Location could not be geocoded or no fuel stations near route"),
            502: OpenApiResponse(description="Upstream routing API call failed"),
            503: OpenApiResponse(description="Fuel station index not loaded"),
        },
        examples=[
            OpenApiExample(
                "New York → Los Angeles",
                summary="Cross-country trip",
                value={"start": "New York, NY", "finish": "Los Angeles, CA"},
                request_only=True,
            ),
            OpenApiExample(
                "Chicago → Dallas",
                summary="Midwest to Texas",
                value={"start": "Chicago, IL", "finish": "Dallas, TX"},
                request_only=True,
            ),
            OpenApiExample(
                "Raw coordinates",
                summary="Using lat,lon directly (skips geocoding)",
                value={"start": "40.7128,-74.0060", "finish": "34.0522,-118.2437"},
                request_only=True,
            ),
        ],
    )
    def post(self, request: Request) -> Response:
        t0 = time.perf_counter()

        # ── 1. Validate input ──────────────────────────────────────────────────
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_input: str = serializer.validated_data["start"]
        finish_input: str = serializer.validated_data["finish"]

        # ── 2. Geocode start & finish ──────────────────────────────────────────
        try:
            start_lat, start_lon = geocode(start_input)
            finish_lat, finish_lon = geocode(finish_input)
        except GeocoderError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # ── 3. Fetch route (1 ORS call, cached afterwards) ────────────────────
        try:
            route_data = get_route(start_lat, start_lon, finish_lat, finish_lon)
        except RouterError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        polyline = route_data["polyline"]
        total_distance_miles = route_data["total_distance_miles"]
        duration_seconds = route_data["duration_seconds"]

        # ── 4. Fuel station lookup & milepost assignment ───────────────────────
        if not FuelStationIndex.is_loaded():
            return Response(
                {"error": "Fuel station index not loaded. Check FUEL_DATA_PATH setting."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        corridor_miles = getattr(settings, "ROUTE_CORRIDOR_MILES", 50)
        nearby_df = FuelStationIndex.find_near_polyline(polyline, corridor_miles)

        if nearby_df.empty:
            return Response(
                {
                    "error": "No fuel stations found near this route. "
                             "Try increasing ROUTE_CORRIDOR_MILES or check your fuel data."
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        cum_dist = _cumulative_distances(polyline)
        stations_with_mileposts = assign_mileposts(
            nearby_df, polyline, cum_dist, corridor_miles
        )

        # ── 5. Run greedy optimizer ────────────────────────────────────────────
        max_range = getattr(settings, "VEHICLE_MAX_RANGE_MILES", 500)
        mpg = getattr(settings, "VEHICLE_MPG", 10)

        optimal_stops, total_cost, total_gallons = find_optimal_stops(
            stations_with_mileposts,
            total_distance_miles,
            max_range=max_range,
            mpg=mpg,
        )

        # ── 6. Build response ──────────────────────────────────────────────────
        map_url = build_map_url(polyline, optimal_stops)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.info(
            "Route %s → %s | %.1f mi | %d stops | $%.2f | %dms",
            start_input,
            finish_input,
            total_distance_miles,
            len(optimal_stops),
            total_cost,
            elapsed_ms,
        )

        response_data = {
            "route": {
                "start": start_input,
                "finish": finish_input,
                "start_lat": start_lat,
                "start_lon": start_lon,
                "finish_lat": finish_lat,
                "finish_lon": finish_lon,
                "total_distance_miles": total_distance_miles,
                "estimated_duration_hours": round(duration_seconds / 3600, 2),
                "route_geometry": polyline,
                "map_url": map_url,
            },
            "fuel_stops": optimal_stops,
            "total_fuel_cost": total_cost,
            "total_gallons": total_gallons,
            "vehicle_range_miles": max_range,
            "vehicle_mpg": mpg,
        }

        return Response(response_data, status=status.HTTP_200_OK)
