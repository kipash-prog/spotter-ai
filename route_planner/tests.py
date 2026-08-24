"""
Tests for the route_planner app.

Covers:
- FuelOptimizer algorithm correctness
- FuelStationIndex spatial lookup
- Geocoder coordinate passthrough
- RouteRequestSerializer validation
- API endpoint (mocked external calls)
"""

import json
import math
import os
import tempfile
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from route_planner.services.fuel_optimizer import (
    assign_mileposts,
    find_optimal_stops,
    _haversine,
    _cumulative_distances,
)
from route_planner.services.geocoder import geocode, GeocoderError
from route_planner.serializers import RouteRequestSerializer


# ── Helper factories ────────────────────────────────────────────────────────────

def make_station(milepost: float, price: float, name: str = "Test Station") -> dict:
    return {
        "milepost": milepost,
        "price_per_gallon": price,
        "name": name,
        "address": "123 Test Rd",
        "city": "Testville",
        "state": "TX",
        "lat": 30.0,
        "lon": -95.0,
    }


# ── Haversine tests ─────────────────────────────────────────────────────────────

class HaversineTests(TestCase):
    def test_same_point_is_zero(self):
        self.assertAlmostEqual(_haversine(40.0, -74.0, 40.0, -74.0), 0.0, places=5)

    def test_known_distance(self):
        # NYC to LA is roughly 2451 miles as-the-crow-flies
        dist = _haversine(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertGreater(dist, 2000)
        self.assertLess(dist, 3000)

    def test_symmetry(self):
        d1 = _haversine(40.0, -74.0, 34.0, -118.0)
        d2 = _haversine(34.0, -118.0, 40.0, -74.0)
        self.assertAlmostEqual(d1, d2, places=8)


# ── Fuel optimizer tests ────────────────────────────────────────────────────────

class FuelOptimizerTests(TestCase):

    def test_no_stops_needed_when_destination_in_range(self):
        """Trip shorter than max range requires no stops."""
        stations = [
            make_station(100, 3.50),
            make_station(200, 3.20),
        ]
        stops, cost, gallons = find_optimal_stops(
            stations, total_distance_miles=400, max_range=500, mpg=10
        )
        self.assertEqual(stops, [])
        self.assertEqual(cost, 0.0)
        self.assertEqual(gallons, 0.0)

    def test_single_mandatory_stop(self):
        """Trip of 600 miles must stop at least once (range=500)."""
        stations = [make_station(300, 3.50, "MidPoint")]
        stops, cost, gallons = find_optimal_stops(
            stations, total_distance_miles=600, max_range=500, mpg=10
        )
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]["name"], "MidPoint")
        self.assertGreater(cost, 0)

    def test_prefers_cheaper_station(self):
        """
        Two stations at mile 200 (cheap) and mile 100 (expensive).
        Optimizer should choose cheaper mile-200 station.
        """
        stations = [
            make_station(100, 4.00, "Expensive"),
            make_station(200, 2.50, "Cheap"),
        ]
        stops, cost, gallons = find_optimal_stops(
            stations, total_distance_miles=600, max_range=500, mpg=10
        )
        # Should not stop at the expensive one if cheap is reachable
        stop_names = [s["name"] for s in stops]
        self.assertIn("Cheap", stop_names)

    def test_cost_calculation_correct(self):
        """Verify cost = gallons × price."""
        stations = [make_station(400, 3.00, "MidStop")]
        stops, total_cost, total_gallons = find_optimal_stops(
            stations, total_distance_miles=800, max_range=500, mpg=10
        )
        computed = sum(s["gallons_purchased"] * s["price_per_gallon"] for s in stops)
        self.assertAlmostEqual(computed, total_cost, places=1)

    def test_multiple_stops_long_route(self):
        """Cross-country route (2800 miles) should have multiple stops."""
        stations = [
            make_station(400, 3.50),
            make_station(800, 3.20),
            make_station(1200, 3.80),
            make_station(1600, 3.10),
            make_station(2000, 3.60),
            make_station(2400, 3.30),
        ]
        stops, cost, gallons = find_optimal_stops(
            stations, total_distance_miles=2800, max_range=500, mpg=10
        )
        self.assertGreater(len(stops), 1)
        self.assertGreater(cost, 0)

    def test_tank_never_exceeds_capacity(self):
        """Gallons purchased at any stop should not overfill tank."""
        stations = [
            make_station(100, 4.00),
            make_station(250, 2.50),
            make_station(450, 3.00),
        ]
        stops, _, _ = find_optimal_stops(
            stations, total_distance_miles=700, max_range=500, mpg=10
        )
        tank_capacity = 500 / 10  # 50 gallons
        for stop in stops:
            self.assertLessEqual(
                stop["gallons_purchased"],
                tank_capacity + 0.01,  # tiny float tolerance
                msg=f"Stop {stop['name']} overfilled tank",
            )

    def test_cumulative_distances(self):
        """Simple straight polyline cumulative distance check."""
        # Two points ~111 km apart (1 degree latitude ≈ 69 miles)
        polyline = [[0.0, 0.0], [0.0, 1.0]]  # [lon, lat]
        cum = _cumulative_distances(polyline)
        self.assertEqual(len(cum), 2)
        self.assertAlmostEqual(cum[0], 0.0)
        self.assertAlmostEqual(cum[1], 69.0, delta=2.0)  # ~69 miles per degree lat


# ── Geocoder tests ──────────────────────────────────────────────────────────────

class GeocoderTests(TestCase):

    def test_raw_coordinates_parsed(self):
        """'lat,lon' string should be parsed without any API call."""
        lat, lon = geocode("40.7128,-74.0060")
        self.assertAlmostEqual(lat, 40.7128, places=4)
        self.assertAlmostEqual(lon, -74.0060, places=4)

    def test_raw_coordinates_with_spaces(self):
        lat, lon = geocode("  34.0522 , -118.2437  ")
        self.assertAlmostEqual(lat, 34.0522, places=4)
        self.assertAlmostEqual(lon, -118.2437, places=4)

    @override_settings(ORS_API_KEY="")
    def test_raises_error_without_api_key(self):
        with self.assertRaises(GeocoderError):
            geocode("New York, NY")


# ── Serializer tests ────────────────────────────────────────────────────────────

class RouteRequestSerializerTests(TestCase):

    def test_valid_data(self):
        s = RouteRequestSerializer(data={"start": "New York, NY", "finish": "Los Angeles, CA"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_missing_start(self):
        s = RouteRequestSerializer(data={"finish": "Los Angeles, CA"})
        self.assertFalse(s.is_valid())
        self.assertIn("start", s.errors)

    def test_missing_finish(self):
        s = RouteRequestSerializer(data={"start": "New York, NY"})
        self.assertFalse(s.is_valid())
        self.assertIn("finish", s.errors)

    def test_same_start_and_finish_rejected(self):
        s = RouteRequestSerializer(data={"start": "Chicago, IL", "finish": "Chicago, IL"})
        self.assertFalse(s.is_valid())

    def test_empty_start_rejected(self):
        s = RouteRequestSerializer(data={"start": "  ", "finish": "LA"})
        self.assertFalse(s.is_valid())


# ── API integration tests (mocked) ─────────────────────────────────────────────

MOCK_POLYLINE = [
    [-74.0060, 40.7128],  # NYC start
    [-86.0, 39.0],        # midpoint
    [-118.2437, 34.0522], # LA finish
]

MOCK_ROUTE = {
    "polyline": MOCK_POLYLINE,
    "total_distance_miles": 2798.5,
    "duration_seconds": 144000.0,
    "bbox": [-118.2437, 34.0522, -74.0060, 40.7128],
}


class RoutePlannerAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

    @patch("route_planner.views.geocode")
    @patch("route_planner.views.get_route")
    @patch("route_planner.views.FuelStationIndex")
    @patch("route_planner.views.assign_mileposts")
    @patch("route_planner.views.find_optimal_stops")
    def test_successful_route(
        self,
        mock_optimizer,
        mock_assign,
        mock_index,
        mock_get_route,
        mock_geocode,
    ):
        # Setup mocks
        mock_geocode.side_effect = [
            (40.7128, -74.0060),   # start
            (34.0522, -118.2437),  # finish
        ]
        mock_get_route.return_value = MOCK_ROUTE
        mock_index.is_loaded.return_value = True

        import pandas as pd
        mock_index.find_near_polyline.return_value = pd.DataFrame([
            {"lat": 39.0, "lon": -86.0, "price_per_gallon": 3.20,
             "name": "Test Stop", "address": "100 Hwy", "city": "Gary", "state": "IN"}
        ])

        mock_assign.return_value = [
            {"milepost": 800, "price_per_gallon": 3.20, "name": "Test Stop",
             "address": "100 Hwy", "city": "Gary", "state": "IN",
             "lat": 39.0, "lon": -86.0}
        ]

        mock_optimizer.return_value = (
            [{
                "name": "Test Stop", "address": "100 Hwy", "city": "Gary",
                "state": "IN", "lat": 39.0, "lon": -86.0,
                "price_per_gallon": 3.20, "distance_from_start_miles": 800.0,
                "gallons_purchased": 25.0, "cost_at_this_stop": 80.0,
            }],
            839.55,
            261.98,
        )

        response = self.client.post(
            "/api/v1/route/",
            data=json.dumps({"start": "New York, NY", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("route", data)
        self.assertIn("fuel_stops", data)
        self.assertIn("total_fuel_cost", data)
        self.assertIn("total_gallons", data)
        self.assertEqual(data["vehicle_range_miles"], 500)
        self.assertEqual(data["vehicle_mpg"], 10)

    def test_missing_body_returns_400(self):
        response = self.client.post(
            "/api/v1/route/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_same_start_finish_returns_400(self):
        response = self.client.post(
            "/api/v1/route/",
            data=json.dumps({"start": "Denver, CO", "finish": "Denver, CO"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("route_planner.views.geocode", side_effect=GeocoderError("Location not found"))
    def test_geocoder_error_returns_422(self, _):
        response = self.client.post(
            "/api/v1/route/",
            data=json.dumps({"start": "Blarghhh, ZZ", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.json())
