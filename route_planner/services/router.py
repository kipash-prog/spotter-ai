"""
Router service — fetches a driving route from OpenRouteService.

Makes exactly ONE API call per unique (start, finish) pair.
Results are cached using Django's cache framework so repeated
requests for the same route hit zero external APIs.
"""

import hashlib
import logging
from typing import Any, Dict, List, Tuple

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
_METERS_PER_MILE = 1609.344


class RouterError(Exception):
    """Raised when routing fails."""


def _cache_key(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> str:
    raw = f"{start_lat:.6f},{start_lon:.6f}|{end_lat:.6f},{end_lon:.6f}"
    return "route:" + hashlib.md5(raw.encode()).hexdigest()


def get_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> Dict[str, Any]:
    """
    Return route information between two coordinate pairs.

    Returns a dict with:
        - polyline: List of [lon, lat] pairs
        - total_distance_miles: float
        - duration_seconds: float
        - bbox: [min_lon, min_lat, max_lon, max_lat]

    The result is cached for 1 hour; only the first call hits ORS.
    """
    key = _cache_key(start_lat, start_lon, end_lat, end_lon)
    cached = cache.get(key)
    if cached is not None:
        logger.debug("Route cache HIT for key %s", key)
        return cached

    logger.debug("Route cache MISS — calling ORS API …")

    api_key = getattr(settings, "ORS_API_KEY", "")
    if not api_key:
        raise RouterError(
            "ORS_API_KEY is not configured. "
            "Set it in your .env file and restart the server."
        )

    payload = {
        "coordinates": [
            [start_lon, start_lat],
            [end_lon, end_lat],
        ],
        "instructions": False,
        "geometry_simplify": False,
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json, application/geo+json",
    }

    try:
        resp = requests.post(
            _ORS_DIRECTIONS_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RouterError(f"ORS routing request failed: {exc}") from exc

    data = resp.json()

    try:
        feature = data["features"][0]
        properties = feature["properties"]
        summary = properties["summary"]
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]  # list of [lon, lat]
        bbox = data.get("bbox", [])
    except (KeyError, IndexError) as exc:
        raise RouterError(f"Unexpected ORS response format: {exc}") from exc

    distance_miles = summary["distance"] / _METERS_PER_MILE
    duration_seconds = summary["duration"]

    result = {
        "polyline": coordinates,
        "total_distance_miles": round(distance_miles, 2),
        "duration_seconds": round(duration_seconds, 0),
        "bbox": bbox,
    }

    # Cache for 1 hour
    cache.set(key, result, timeout=3600)
    logger.info(
        "Route fetched: %.1f miles, %.0f seconds; polyline has %d points.",
        distance_miles,
        duration_seconds,
        len(coordinates),
    )
    return result


def build_map_url(polyline: List[List[float]], stops: List[Dict]) -> str:
    """
    Build a shareable link to an OpenRouteService maps page
    showing the route with waypoints.

    ORS Maps URL format: https://maps.openrouteservice.org/directions?...
    We encode start and end as waypoints; full geometry is in the polyline.
    """
    if not polyline:
        return ""
    start_lon, start_lat = polyline[0]
    end_lon, end_lat = polyline[-1]

    waypoints = f"{start_lon},{start_lat}|{end_lon},{end_lat}"
    return (
        f"https://maps.openrouteservice.org/directions?"
        f"n1={start_lat}&e1={start_lon}&n2={end_lat}&e2={end_lon}&a=false&b=0&c=0&k1=en-US&k2=km"
    )
