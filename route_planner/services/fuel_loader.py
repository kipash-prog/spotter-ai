"""
FuelStationIndex — loads fuel_prices.csv at startup and provides
fast spatial lookups via a scipy KD-Tree.

The index is a module-level singleton built once in AppConfig.ready()
and reused for all subsequent requests.
"""

import logging
import math
import os
from typing import List, Tuple, Dict, Any

import numpy as np
import pandas as pd
from scipy.spatial import KDTree

from django.conf import settings

logger = logging.getLogger(__name__)

# ── Earth radius in miles ──────────────────────────────────────────────────────
_EARTH_RADIUS_MILES = 3958.8


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in miles between two lat/lon points."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


class FuelStationIndex:
    """
    Singleton that holds all fuel stations in memory and exposes a
    spatial search method.

    Usage:
        stations = FuelStationIndex.find_near_polyline(polyline, corridor_miles=50)
    """

    _df: pd.DataFrame = None          # full station DataFrame
    _tree: KDTree = None              # KD-Tree of (lat_rad, lon_rad) coords
    _coords_rad: np.ndarray = None    # matching coordinate array in radians
    _loaded: bool = False

    @classmethod
    def load(cls) -> None:
        """Load CSV and build the KD-Tree. Called once at startup."""
        path = getattr(settings, "FUEL_DATA_PATH", "data/fuel_prices.csv")
        if not os.path.exists(path):
            logger.error("Fuel data file not found: %s", path)
            return

        logger.info("Loading fuel station data from %s …", path)
        df = pd.read_csv(path)

        # Validate required columns
        required = {"lat", "lon", "price_per_gallon", "name"}
        missing = required - set(df.columns)
        if missing:
            logger.error("Fuel CSV missing columns: %s", missing)
            return

        df = df.dropna(subset=["lat", "lon", "price_per_gallon"])
        df = df.reset_index(drop=True)

        # Build KD-Tree using 3-D unit-sphere coordinates for accurate
        # great-circle nearest-neighbour queries.
        lats_r = np.radians(df["lat"].values)
        lons_r = np.radians(df["lon"].values)
        xs = np.cos(lats_r) * np.cos(lons_r)
        ys = np.cos(lats_r) * np.sin(lons_r)
        zs = np.sin(lats_r)
        coords_3d = np.column_stack([xs, ys, zs])

        cls._df = df
        cls._tree = KDTree(coords_3d)
        cls._coords_rad = np.column_stack([lats_r, lons_r])
        cls._loaded = True
        logger.info("Fuel station index ready — %d stations loaded.", len(df))

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._loaded

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _to_3d(lat_deg: float, lon_deg: float) -> np.ndarray:
        lat_r = math.radians(lat_deg)
        lon_r = math.radians(lon_deg)
        return np.array([
            math.cos(lat_r) * math.cos(lon_r),
            math.cos(lat_r) * math.sin(lon_r),
            math.sin(lat_r),
        ])

    @classmethod
    def _miles_to_chord(cls, miles: float) -> float:
        """Convert a great-circle distance (miles) to a 3-D chord length."""
        angle = miles / _EARTH_RADIUS_MILES          # radians
        return 2 * math.sin(angle / 2)               # chord on unit sphere

    # ── Public API ─────────────────────────────────────────────────────────────

    @classmethod
    def find_stations_within_miles(
        cls,
        lat: float,
        lon: float,
        radius_miles: float,
    ) -> List[Dict[str, Any]]:
        """Return all stations within *radius_miles* of the given point."""
        if not cls._loaded:
            return []
        query_pt = cls._to_3d(lat, lon)
        chord = cls._miles_to_chord(radius_miles)
        idxs = cls._tree.query_ball_point(query_pt, r=chord)
        return cls._df.iloc[idxs].to_dict(orient="records")

    @classmethod
    def find_near_polyline(
        cls,
        polyline: List[Tuple[float, float]],
        corridor_miles: float = 50,
    ) -> pd.DataFrame:
        """
        Return all fuel stations within *corridor_miles* of *any* point on the
        route polyline.

        The polyline is a list of [lon, lat] pairs (ORS convention).

        Returns a deduplicated DataFrame sorted by station index.
        """
        if not cls._loaded or not polyline:
            return pd.DataFrame()

        chord = cls._miles_to_chord(corridor_miles)
        all_idxs: set = set()

        # Sub-sample the polyline — check every N-th point to limit work
        # while still covering the corridor.  For a 500-mile trip the ORS
        # polyline typically has ~1 000–5 000 points; checking every 20th
        # keeps the loop under 250 iterations.
        step = max(1, len(polyline) // 250)
        for i in range(0, len(polyline), step):
            lon, lat = polyline[i]
            query_pt = cls._to_3d(lat, lon)
            idxs = cls._tree.query_ball_point(query_pt, r=chord)
            all_idxs.update(idxs)

        # Always include the last point
        lon, lat = polyline[-1]
        idxs = cls._tree.query_ball_point(cls._to_3d(lat, lon), r=chord)
        all_idxs.update(idxs)

        if not all_idxs:
            return pd.DataFrame()

        return cls._df.iloc[sorted(all_idxs)].copy().reset_index(drop=True)
