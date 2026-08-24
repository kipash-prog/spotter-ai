"""
Geocoder service — converts a human-readable US address / city name
to (lat, lon) using the OpenRouteService Geocoding API.

Falls back to treating the input as "lat,lon" if it looks like coordinates.
"""

import logging
import re
from typing import Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
_COORD_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")


class GeocoderError(Exception):
    """Raised when a location cannot be geocoded."""


def geocode(location: str) -> Tuple[float, float]:
    """
    Convert *location* (address string or "lat,lon") to (lat, lon).

    Raises GeocoderError if the location cannot be resolved.
    """
    # 1. Try parsing raw coordinates first — zero API calls
    match = _COORD_RE.match(location)
    if match:
        lat, lon = float(match.group(1)), float(match.group(2))
        logger.debug("Parsed raw coordinates: (%s, %s)", lat, lon)
        return lat, lon

    # 2. Call ORS Geocoding API
    api_key = getattr(settings, "ORS_API_KEY", "")
    if not api_key:
        raise GeocoderError(
            "ORS_API_KEY is not configured. "
            "Set it in your .env file and restart the server."
        )

    params = {
        "api_key": api_key,
        "text": location,
        "boundary.country": "US",
        "size": 1,
    }

    try:
        resp = requests.get(_ORS_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GeocoderError(f"Geocoding request failed: {exc}") from exc

    data = resp.json()
    features = data.get("features", [])
    if not features:
        raise GeocoderError(
            f"Could not geocode location: '{location}'. "
            "Try a more specific address or use 'lat,lon' format."
        )

    coords = features[0]["geometry"]["coordinates"]  # [lon, lat]
    lon, lat = coords[0], coords[1]
    logger.debug("Geocoded '%s' → (%s, %s)", location, lat, lon)
    return lat, lon
