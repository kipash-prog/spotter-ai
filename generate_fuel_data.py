"""
Script to generate realistic US fuel station dataset.
Run once: python generate_fuel_data.py
"""
import csv
import random
import os

random.seed(42)

# Real US fuel station chains
CHAINS = [
    "Pilot Flying J", "Love's Travel Stop", "TravelCenters of America",
    "Petro Stopping Centers", "Kwik Trip", "Casey's General Store",
    "Speedway", "Circle K", "Wawa", "Sheetz", "Sunoco", "BP",
    "Chevron", "Shell", "ExxonMobil", "Marathon", "Valero", "Phillips 66",
    "Conoco", "Flying J", "Sapp Bros.", "Iowa 80", "Road Ranger"
]

# Realistic US locations along major highway corridors
# Format: (state, city, approx_lat, approx_lon)
LOCATIONS = [
    # I-90/I-94 northern corridor
    ("WA", "Seattle", 47.6062, -122.3321),
    ("WA", "Spokane", 47.6588, -117.4260),
    ("ID", "Coeur d'Alene", 47.6777, -116.7805),
    ("MT", "Missoula", 46.8721, -113.9940),
    ("MT", "Billings", 45.7833, -108.5007),
    ("MT", "Miles City", 46.4083, -105.8406),
    ("ND", "Bismarck", 46.8083, -100.7837),
    ("ND", "Fargo", 46.8772, -96.7898),
    ("MN", "Minneapolis", 44.9778, -93.2650),
    ("WI", "Madison", 43.0731, -89.4012),
    ("IL", "Chicago", 41.8781, -87.6298),
    ("IN", "Gary", 41.5934, -87.3465),
    ("OH", "Cleveland", 41.4993, -81.6944),
    ("PA", "Erie", 42.1292, -80.0851),
    ("NY", "Buffalo", 42.8864, -78.8784),
    ("NY", "Albany", 42.6526, -73.7562),
    ("MA", "Boston", 42.3601, -71.0589),

    # I-80 east-west corridor
    ("CA", "San Francisco", 37.7749, -122.4194),
    ("CA", "Sacramento", 38.5816, -121.4944),
    ("NV", "Reno", 39.5296, -119.8138),
    ("NV", "Elko", 40.8324, -115.7631),
    ("UT", "Salt Lake City", 40.7608, -111.8910),
    ("UT", "Provo", 40.2338, -111.6585),
    ("WY", "Green River", 41.5275, -109.4665),
    ("WY", "Rawlins", 41.7911, -107.2387),
    ("WY", "Laramie", 41.3114, -105.5911),
    ("NE", "Cheyenne", 41.1400, -104.8202),
    ("NE", "North Platte", 41.1239, -100.7654),
    ("NE", "Kearney", 40.6993, -99.0817),
    ("NE", "Lincoln", 40.8136, -96.7026),
    ("IA", "Omaha", 41.2565, -95.9345),
    ("IA", "Des Moines", 41.5868, -93.6250),
    ("IL", "Davenport", 41.5236, -90.5776),
    ("IN", "Indianapolis", 39.7684, -86.1581),
    ("OH", "Columbus", 39.9612, -82.9988),
    ("PA", "Pittsburgh", 40.4406, -79.9959),
    ("NJ", "Newark", 40.7357, -74.1724),
    ("NY", "New York City", 40.7128, -74.0060),

    # I-40 southern corridor
    ("CA", "Los Angeles", 34.0522, -118.2437),
    ("CA", "Barstow", 34.8958, -116.9719),
    ("AZ", "Needles", 34.8481, -114.6144),
    ("AZ", "Kingman", 35.1895, -114.0530),
    ("AZ", "Flagstaff", 35.1983, -111.6513),
    ("AZ", "Winslow", 35.0242, -110.6973),
    ("NM", "Gallup", 35.5281, -108.7426),
    ("NM", "Albuquerque", 35.0844, -106.6504),
    ("NM", "Santa Rosa", 34.9387, -104.6824),
    ("TX", "Amarillo", 35.2220, -101.8313),
    ("TX", "Shamrock", 35.2190, -100.2488),
    ("OK", "Oklahoma City", 35.4676, -97.5164),
    ("OK", "Tulsa", 36.1540, -95.9928),
    ("AR", "Fort Smith", 35.3859, -94.3985),
    ("AR", "Little Rock", 34.7465, -92.2896),
    ("TN", "Memphis", 35.1495, -90.0490),
    ("TN", "Nashville", 36.1627, -86.7816),
    ("NC", "Asheville", 35.5951, -82.5515),
    ("SC", "Spartanburg", 34.9496, -81.9321),
    ("SC", "Columbia", 34.0007, -81.0348),
    ("NC", "Charlotte", 35.2271, -80.8431),
    ("NC", "Raleigh", 35.7796, -78.6382),
    ("NC", "Wilmington", 34.2257, -77.9447),

    # I-10 southern route
    ("FL", "Jacksonville", 30.3322, -81.6557),
    ("FL", "Tallahassee", 30.4518, -84.2807),
    ("FL", "Pensacola", 30.4213, -87.2169),
    ("AL", "Mobile", 30.6954, -88.0399),
    ("MS", "Biloxi", 30.3960, -88.8853),
    ("LA", "New Orleans", 29.9511, -90.0715),
    ("LA", "Baton Rouge", 30.4515, -91.1871),
    ("TX", "Houston", 29.7604, -95.3698),
    ("TX", "San Antonio", 29.4241, -98.4936),
    ("TX", "El Paso", 31.7619, -106.4850),
    ("NM", "Las Cruces", 32.3199, -106.7637),
    ("AZ", "Tucson", 32.2226, -110.9747),
    ("AZ", "Phoenix", 33.4484, -112.0740),
    ("CA", "Blythe", 33.6103, -114.5885),
    ("CA", "Indio", 33.7206, -116.2156),
    ("CA", "San Bernardino", 34.1083, -117.2898),

    # I-35 north-south
    ("TX", "Laredo", 27.5306, -99.4803),
    ("TX", "Austin", 30.2672, -97.7431),
    ("TX", "Waco", 31.5493, -97.1467),
    ("TX", "Dallas", 32.7767, -96.7970),
    ("TX", "Fort Worth", 32.7555, -97.3308),
    ("OK", "Ardmore", 34.1743, -97.1436),
    ("KS", "Wichita", 37.6872, -97.3301),
    ("KS", "Salina", 38.8403, -97.6114),
    ("KS", "Kansas City", 39.1155, -94.6268),
    ("MO", "Kansas City", 39.0997, -94.5786),
    ("IA", "Ames", 42.0347, -93.6200),
    ("MN", "Albert Lea", 43.6480, -93.3682),
    ("MN", "St Paul", 44.9537, -93.0900),
    ("MN", "Duluth", 46.7867, -92.1005),

    # I-95 east coast
    ("FL", "Miami", 25.7617, -80.1918),
    ("FL", "Orlando", 28.5383, -81.3792),
    ("GA", "Savannah", 32.0835, -81.0998),
    ("GA", "Atlanta", 33.7490, -84.3880),
    ("SC", "Florence", 34.1954, -79.7626),
    ("VA", "Richmond", 37.5407, -77.4360),
    ("VA", "Fredericksburg", 38.3032, -77.4605),
    ("DC", "Washington", 38.9072, -77.0369),
    ("MD", "Baltimore", 39.2904, -76.6122),
    ("DE", "Wilmington", 39.7447, -75.5484),
    ("PA", "Philadelphia", 39.9526, -75.1652),
    ("NJ", "Trenton", 40.2170, -74.7429),
    ("CT", "Bridgeport", 41.1865, -73.1952),
    ("CT", "Hartford", 41.7658, -72.6851),
    ("MA", "Providence", 41.8240, -71.4128),

    # Mountain / southwest
    ("CO", "Denver", 39.7392, -104.9903),
    ("CO", "Colorado Springs", 38.8339, -104.8214),
    ("CO", "Pueblo", 38.2544, -104.6091),
    ("CO", "Grand Junction", 39.0639, -108.5506),
    ("UT", "St. George", 37.0965, -113.5684),
    ("NV", "Las Vegas", 36.1699, -115.1398),
    ("NV", "Winnemucca", 40.9730, -117.7357),
    ("ID", "Boise", 43.6150, -116.2023),
    ("ID", "Twin Falls", 42.5629, -114.4609),
    ("OR", "Portland", 45.5051, -122.6750),
    ("OR", "Salem", 44.9429, -123.0351),
    ("OR", "Eugene", 44.0521, -123.0868),

    # Midwest additions
    ("MI", "Detroit", 42.3314, -83.0458),
    ("MI", "Lansing", 42.7325, -84.5555),
    ("MI", "Flint", 43.0125, -83.6875),
    ("OH", "Toledo", 41.6639, -83.5552),
    ("OH", "Dayton", 39.7589, -84.1916),
    ("OH", "Cincinnati", 39.1031, -84.5120),
    ("KY", "Louisville", 38.2527, -85.7585),
    ("KY", "Lexington", 38.0406, -84.5037),
    ("TN", "Knoxville", 35.9606, -83.9207),
    ("TN", "Chattanooga", 35.0456, -85.3097),
    ("AL", "Birmingham", 33.5186, -86.8104),
    ("AL", "Montgomery", 32.3668, -86.2999),
    ("MS", "Jackson", 32.2988, -90.1848),
    ("MO", "St. Louis", 38.6270, -90.1994),
    ("MO", "Springfield", 37.2153, -93.2982),
    ("AR", "Fayetteville", 36.0626, -94.1574),
    ("IN", "Fort Wayne", 41.0793, -85.1394),
    ("IN", "South Bend", 41.6764, -86.2520),
    ("WI", "Milwaukee", 43.0389, -87.9065),
    ("WI", "Green Bay", 44.5133, -88.0133),
    ("MN", "Rochester", 44.0234, -92.4631),
]

def generate_price(state):
    """Generate realistic fuel price by state (some states cheaper than others)."""
    base_prices = {
        "CA": 4.80, "WA": 4.20, "OR": 4.10, "NV": 4.00, "HI": 5.50,
        "AK": 4.40, "IL": 3.95, "NY": 4.05, "PA": 3.75, "MA": 3.85,
        "CT": 3.90, "NJ": 3.65, "MD": 3.60, "DC": 4.10, "DE": 3.55,
        "FL": 3.50, "GA": 3.30, "AL": 3.25, "MS": 3.20, "LA": 3.15,
        "TX": 3.10, "OK": 3.05, "KS": 3.15, "NE": 3.20, "SD": 3.25,
        "ND": 3.30, "MN": 3.40, "IA": 3.30, "MO": 3.20, "AR": 3.15,
        "TN": 3.20, "KY": 3.25, "OH": 3.35, "IN": 3.40, "MI": 3.50,
        "WI": 3.45, "CO": 3.55, "AZ": 3.50, "NM": 3.35, "UT": 3.45,
        "ID": 3.60, "MT": 3.50, "WY": 3.30, "SC": 3.25, "NC": 3.30,
        "VA": 3.40, "WV": 3.35,
    }
    base = base_prices.get(state, 3.50)
    # Add slight random variation ±$0.25
    return round(base + random.uniform(-0.25, 0.25), 3)

def main():
    os.makedirs("data", exist_ok=True)
    rows = []
    station_id = 1

    for state, city, lat, lon in LOCATIONS:
        # Generate 2-5 stations per location with slight coordinate offsets
        count = random.randint(2, 5)
        for i in range(count):
            lat_offset = random.uniform(-0.15, 0.15)
            lon_offset = random.uniform(-0.15, 0.15)
            chain = random.choice(CHAINS)
            price = generate_price(state)
            rows.append({
                "id": station_id,
                "name": chain,
                "address": f"{random.randint(100, 9999)} Highway Dr, {city}, {state}",
                "city": city,
                "state": state,
                "lat": round(lat + lat_offset, 6),
                "lon": round(lon + lon_offset, 6),
                "price_per_gallon": price,
            })
            station_id += 1

    with open("data/fuel_prices.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "address", "city", "state", "lat", "lon", "price_per_gallon"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} fuel stations in data/fuel_prices.csv")

if __name__ == "__main__":
    main()
