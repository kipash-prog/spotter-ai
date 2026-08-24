"""
Build city-to-coords lookup from GeoNames US data.
Run AFTER downloading US.txt via preprocess_fuel_data.py.

GeoNames format (tab-separated):
  geonameid, name, asciiname, alternatenames, latitude, longitude,
  feature_class, feature_code, country_code, cc2, admin1_code (state),
  admin2_code, admin3_code, admin4_code, population, elevation,
  dem, timezone, modification_date

We filter feature_class=P (populated places) and build a JSON cache.
"""

import csv
import json
import os

GEONAMES_FILE = "data/US.txt"
OUTPUT_FILE = "data/geocode_cache.json"

STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

def build():
    if not os.path.exists(GEONAMES_FILE):
        print(f"ERROR: {GEONAMES_FILE} not found. Run the download first.")
        return

    # Load existing cache (don't overwrite Nominatim results)
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Existing cache: {len(existing)} entries")

    print(f"Building city lookup from {GEONAMES_FILE} …")
    new_entries = 0
    lookup = dict(existing)  # start from existing

    with open(GEONAMES_FILE, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 11:
                continue
            name = parts[1]          # place name
            lat = float(parts[4])
            lon = float(parts[5])
            feature_class = parts[6]  # P = populated place
            state_code = parts[10]   # admin1_code = 2-digit FIPS or abbreviation

            if feature_class != "P":
                continue

            # GeoNames uses FIPS codes for US admin1 — convert to 2-letter
            state = STATE_FIPS.get(state_code, state_code)

            key = f"{name.lower()}|{state}"
            if key not in lookup:
                lookup[key] = [lat, lon]
                new_entries += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(lookup, f)

    print(f"Done. Added {new_entries} new entries. Total: {len(lookup)}")

if __name__ == "__main__":
    build()
