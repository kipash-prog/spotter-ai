"""
Preprocessing script for Spotter AI fuel prices CSV.

Uses pgeocode (bundled GeoNames zip-code dataset) to resolve city/state
coordinates without any network calls after the first run.

Run once: python preprocess_fuel_data.py
Output:   data/fuel_prices.csv
"""

import csv
import os
import random
import sys
from collections import defaultdict

import pgeocode
import pandas as pd

random.seed(42)

US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
}

STATE_CENTROIDS = {
    "AL":(32.806671,-86.791130),"AK":(61.370716,-152.404419),
    "AZ":(33.729759,-111.431221),"AR":(34.969704,-92.373123),
    "CA":(36.116203,-119.681564),"CO":(39.059811,-105.311104),
    "CT":(41.597782,-72.755371),"DE":(39.318523,-75.507141),
    "FL":(27.766279,-81.686783),"GA":(33.040619,-83.643074),
    "HI":(21.094318,-157.498337),"ID":(44.240459,-114.478828),
    "IL":(40.349457,-88.986137),"IN":(39.849426,-86.258278),
    "IA":(42.011539,-93.210526),"KS":(38.526600,-96.726486),
    "KY":(37.668140,-84.670067),"LA":(31.169960,-91.867805),
    "ME":(44.693947,-69.381927),"MD":(39.063946,-76.802101),
    "MA":(42.230171,-71.530106),"MI":(43.326618,-84.536095),
    "MN":(45.694454,-93.900192),"MS":(32.741646,-89.678696),
    "MO":(38.456085,-92.288368),"MT":(46.921925,-110.454353),
    "NE":(41.125370,-98.268082),"NV":(38.313515,-117.055374),
    "NH":(43.452492,-71.563896),"NJ":(40.298904,-74.521011),
    "NM":(34.840515,-106.248482),"NY":(42.165726,-74.948051),
    "NC":(35.630066,-79.806419),"ND":(47.528912,-99.784012),
    "OH":(40.388783,-82.764915),"OK":(35.565342,-96.928917),
    "OR":(44.572021,-122.070938),"PA":(40.590752,-77.209755),
    "RI":(41.680893,-71.511780),"SC":(33.856892,-80.945007),
    "SD":(44.299782,-99.438828),"TN":(35.747845,-86.692345),
    "TX":(31.054487,-97.563461),"UT":(40.150032,-111.862434),
    "VT":(44.045876,-72.710686),"VA":(37.769337,-78.169968),
    "WA":(47.400902,-121.490494),"WV":(38.491226,-80.954453),
    "WI":(44.268543,-89.616508),"WY":(42.755966,-107.302490),
    "DC":(38.897438,-77.026817),
}

# pgeocode uses the GeoNames zip-code dataset to look up place coordinates.
# We build a city→(lat,lon) lookup by querying every US postal code once.
def build_city_lookup_from_pgeocode() -> dict:
    """
    Build a {(city_lower, state): (lat, lon)} dictionary by scanning all
    US zip codes in the pgeocode dataset (bundled, no network needed after
    the first time pgeocode downloads its ~5 MB data file).
    """
    print("Loading pgeocode US dataset …")
    nomi = pgeocode.Nominatim("us")
    # Access the underlying DataFrame that pgeocode uses
    df = nomi._data  # DataFrame with columns: postal_code, place_name, state_code, lat, lon, ...

    lookup = {}
    for _, row in df.iterrows():
        city = str(row.get("place_name", "")).strip().lower()
        state = str(row.get("state_code", "")).strip().upper()
        lat = row.get("latitude")
        lon = row.get("longitude")
        if city and state and pd.notna(lat) and pd.notna(lon):
            key = (city, state)
            if key not in lookup:  # keep first (most populous) match
                lookup[key] = (float(lat), float(lon))

    print(f"  pgeocode lookup built: {len(lookup):,} unique city/state pairs")
    return lookup


def preprocess():
    rng = random.Random(42)
    input_path = "data/fuel-prices-for-be-assessment.csv"
    output_path = "data/fuel_prices.csv"

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found.")
        sys.exit(1)

    # Build city coordinate lookup
    city_lookup = build_city_lookup_from_pgeocode()

    print(f"Reading {input_path} …")
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
    print(f"  Total rows: {len(all_rows)}")

    # Filter US-only
    us_rows = [r for r in all_rows if r["State"].strip() in US_STATES]
    print(f"  US rows: {len(us_rows)} (dropped {len(all_rows)-len(us_rows)} non-US)")

    # Deduplicate: same OPIS ID + city + state → keep lowest Retail Price
    grouped = defaultdict(list)
    for r in us_rows:
        key = (r["OPIS Truckstop ID"].strip(), r["City"].strip().lower(), r["State"].strip())
        grouped[key].append(r)

    unique = [min(g, key=lambda r: float(r["Retail Price"])) for g in grouped.values()]
    print(f"  Unique US stations after dedup: {len(unique)}")

    # Enrich with coordinates
    fallback_count = 0
    enriched = []
    for r in unique:
        city = r["City"].strip()
        state = r["State"].strip()
        key = (city.lower(), state)

        coords = city_lookup.get(key)
        if coords is None:
            # Try partial match: first word of city name
            first_word = city.lower().split()[0] if city else ""
            for (c, s), v in city_lookup.items():
                if s == state and c.startswith(first_word) and len(first_word) > 3:
                    coords = v
                    break

        if coords is None:
            coords = STATE_CENTROIDS.get(state, (39.5, -98.35))
            fallback_count += 1

        base_lat, base_lon = coords
        # Small jitter so stations in the same city don't stack exactly
        dlat = rng.uniform(-0.04, 0.04)
        dlon = rng.uniform(-0.04, 0.04)

        enriched.append({
            "id": r["OPIS Truckstop ID"].strip(),
            "name": r["Truckstop Name"].strip(),
            "address": r["Address"].strip(),
            "city": city,
            "state": state,
            "lat": round(base_lat + dlat, 6),
            "lon": round(base_lon + dlon, 6),
            "price_per_gallon": round(float(r["Retail Price"]), 4),
        })

    enriched.sort(key=lambda r: (r["state"], r["city"], r["name"]))

    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["id","name","address","city","state","lat","lon","price_per_gallon"]
        )
        w.writeheader()
        w.writerows(enriched)

    print(f"\nDone! {len(enriched)} US fuel stations written to {output_path}")
    print(f"  State-centroid fallbacks: {fallback_count} ({100*fallback_count/len(enriched):.1f}%)")


if __name__ == "__main__":
    preprocess()
