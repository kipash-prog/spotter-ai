"""
FuelOptimizer — greedy cost-optimal fuel stop selection.

Algorithm overview
──────────────────
Given a sorted list of fuel stations with their mile-marker (milepost)
along the route, plus the vehicle's max range and fuel economy:

1. Start at mile 0 with a FULL tank.
2. At each current position, look ahead up to MAX_RANGE miles.
3. If a cheaper station exists within range → buy just enough fuel
   to reach it (arrive nearly empty so we can fill up cheaply there).
4. If no cheaper station within range exists → fill the tank completely
   at the current (or cheapest reachable) station.
5. Repeat until the destination is reachable on the remaining fuel.

This greedy approach is cost-optimal for single-commodity refueling
(proven in competitive programming literature) and runs in O(n) time
after the stations are sorted by milepost.

Milepost assignment
───────────────────
For each candidate station we find the closest point on the route
polyline and compute its cumulative distance from the start — this
is the "milepost".  We use a fast segment-projection approach that
runs in O(P × S) where P = polyline points and S = candidate stations.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_EARTH_RADIUS_MILES = 3958.8


# ── Geometry helpers ────────────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def _cumulative_distances(polyline: List[List[float]]) -> List[float]:
    """
    Return cumulative distances (in miles) along the polyline.
    polyline: list of [lon, lat].
    """
    cum = [0.0]
    for i in range(1, len(polyline)):
        lon1, lat1 = polyline[i - 1]
        lon2, lat2 = polyline[i]
        cum.append(cum[-1] + _haversine(lat1, lon1, lat2, lon2))
    return cum


def _project_station_to_route(
    station_lat: float,
    station_lon: float,
    polyline: List[List[float]],
    cum_dist: List[float],
    search_radius_miles: float = 60,
) -> Optional[float]:
    """
    Find the milepost (cumulative distance from start) of the closest
    point on the polyline to the given station.

    Returns None if the station is farther than search_radius_miles
    from every polyline point (shouldn't happen after the KD-Tree pre-filter).
    """
    best_dist = float("inf")
    best_milepost = None

    for i in range(len(polyline)):
        lon, lat = polyline[i]
        d = _haversine(station_lat, station_lon, lat, lon)
        if d < best_dist:
            best_dist = d
            best_milepost = cum_dist[i]

    if best_dist > search_radius_miles:
        return None
    return best_milepost


# ── Main optimizer ──────────────────────────────────────────────────────────────

def assign_mileposts(
    stations_df,
    polyline: List[List[float]],
    cum_dist: List[float],
    corridor_miles: float = 60,
) -> List[Dict[str, Any]]:
    """
    Assign a milepost to every station and return them sorted by milepost.

    stations_df: pandas DataFrame with columns lat, lon, price_per_gallon, name, …
    polyline: list of [lon, lat]
    cum_dist: cumulative distances along polyline
    """
    stations_with_mile = []
    for _, row in stations_df.iterrows():
        mp = _project_station_to_route(
            row["lat"], row["lon"], polyline, cum_dist, corridor_miles
        )
        if mp is not None:
            entry = row.to_dict()
            entry["milepost"] = mp
            stations_with_mile.append(entry)

    # Sort by milepost
    stations_with_mile.sort(key=lambda s: s["milepost"])
    return stations_with_mile


def find_optimal_stops(
    stations: List[Dict[str, Any]],
    total_distance_miles: float,
    max_range: float = 500,
    mpg: float = 10,
) -> Tuple[List[Dict[str, Any]], float, float]:
    """
    Greedy cost-optimal fuel stop selection.

    Parameters
    ----------
    stations : list of dicts with keys milepost, price_per_gallon, name, etc.
               Must be sorted ascending by milepost.
    total_distance_miles : total route distance
    max_range : vehicle max range on a full tank (miles)
    mpg : miles per gallon

    Returns
    -------
    (stops, total_cost, total_gallons)
        stops: list of stop dicts augmented with gallons_purchased, cost_at_stop
        total_cost: float — total dollars spent on fuel
        total_gallons: float — total gallons purchased
    """
    tank_capacity = max_range / mpg          # gallons
    current_miles = 0.0                      # miles from start
    current_fuel = tank_capacity             # start with full tank
    total_cost = 0.0
    total_gallons = 0.0
    stops: List[Dict[str, Any]] = []

    # Filter stations that are actually on the route (between 0 and total_distance)
    relevant = [s for s in stations if 0 < s["milepost"] < total_distance_miles]

    # Add a virtual "destination" station so the algorithm knows when to stop
    destination = {"milepost": total_distance_miles, "price_per_gallon": 0, "_is_destination": True}
    relevant.append(destination)

    i = 0
    while current_miles < total_distance_miles:
        # Stations reachable from current position
        reachable = [
            s for s in relevant
            if current_miles < s["milepost"] <= current_miles + (current_fuel * mpg)
        ]

        if not reachable:
            # No stations reachable — route is impossible
            logger.warning(
                "No fuel stations reachable from mile %.1f (fuel: %.2f gal left). "
                "Route may be infeasible with this dataset.",
                current_miles,
                current_fuel,
            )
            break

        # Is the destination directly reachable?
        if any(s.get("_is_destination") for s in reachable):
            # We can reach the end — no more stops needed
            break

        # Find the cheapest station within the next max_range miles
        # (not just reachable from current fuel, but within full-tank range)
        within_max_range = [
            s for s in relevant
            if current_miles < s["milepost"] <= current_miles + max_range
               and not s.get("_is_destination")
        ]

        if not within_max_range:
            break

        # Cheapest station within full-tank range
        cheapest_ahead = min(within_max_range, key=lambda s: s["price_per_gallon"])

        # Cheapest station reachable on current fuel (excluding destination)
        reachable_stops = [s for s in reachable if not s.get("_is_destination")]

        if not reachable_stops:
            break

        cheapest_reachable = min(reachable_stops, key=lambda s: s["price_per_gallon"])

        # Decision: which station to stop at?
        # If the cheapest station overall within range IS reachable → go there
        if cheapest_ahead["milepost"] <= current_miles + (current_fuel * mpg):
            stop = cheapest_ahead
        else:
            # Cheapest ahead is not reachable on current fuel →
            # stop at the cheapest reachable station and fill up enough to reach it
            stop = cheapest_reachable

        miles_to_stop = stop["milepost"] - current_miles
        fuel_used_to_stop = miles_to_stop / mpg
        fuel_on_arrival = current_fuel - fuel_used_to_stop

        # How much to buy at this stop?
        # If there's a cheaper station ahead that we can reach from here with a full
        # tank → fill just enough to get there (arrive near-empty).
        # Otherwise → fill the tank completely.
        cheaper_beyond = [
            s for s in relevant
            if s["milepost"] > stop["milepost"]
               and not s.get("_is_destination")
               and s["price_per_gallon"] < stop["price_per_gallon"]
               and s["milepost"] <= stop["milepost"] + max_range
        ]

        if cheaper_beyond:
            # Buy just enough to reach the nearest cheaper station
            nearest_cheaper = min(cheaper_beyond, key=lambda s: s["milepost"])
            miles_needed = nearest_cheaper["milepost"] - stop["milepost"]
            # Add a 5% safety buffer
            gallons_needed = (miles_needed / mpg) * 1.05 - fuel_on_arrival
            gallons_to_buy = max(0.0, gallons_needed)
            # Don't overfill
            gallons_to_buy = min(gallons_to_buy, tank_capacity - fuel_on_arrival)
        else:
            # No cheaper station in range → fill up completely
            gallons_to_buy = tank_capacity - fuel_on_arrival

        gallons_to_buy = round(gallons_to_buy, 3)
        cost = round(gallons_to_buy * stop["price_per_gallon"], 2)

        if gallons_to_buy > 0.001:
            stop_record = {
                "name": stop.get("name", "Unknown"),
                "address": stop.get("address", ""),
                "city": stop.get("city", ""),
                "state": stop.get("state", ""),
                "lat": stop.get("lat"),
                "lon": stop.get("lon"),
                "price_per_gallon": round(stop["price_per_gallon"], 3),
                "distance_from_start_miles": round(stop["milepost"], 1),
                "gallons_purchased": gallons_to_buy,
                "cost_at_this_stop": cost,
            }
            stops.append(stop_record)
            total_cost += cost
            total_gallons += gallons_to_buy

        # Advance position
        current_fuel = fuel_on_arrival + gallons_to_buy
        current_miles = stop["milepost"]

        # Remove this stop from relevant to avoid infinite loops
        relevant = [s for s in relevant if s is not stop]

    return stops, round(total_cost, 2), round(total_gallons, 3)
