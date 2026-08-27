# Spotter AI — Route Fuel Planner API

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![Django REST Framework](https://img.shields.io/badge/DRF-3.15-red.svg)](https://www.django-rest-framework.org/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-brightgreen.svg)](http://localhost:8000/api/docs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A high-performance Django REST API that computes the **cost-optimal fuel stop itinerary** for any road trip within the USA. Given a starting point and destination, it calculates the driving route, identifies the most economical fuel stops along the way based on real world retail fuel prices, and reports the exact total fuel expenditure.

---

## 🚀 Key Highlights & Assignment Requirements

- 🗺️ **Full Route Planning**: Accepts any US start and finish locations (city/state names like `"New York, NY"` or raw `lat,lon` coordinates).
- ⛽ **Cost-Optimal Fuel Stops**: Employs a greedy lookahead algorithm to select the cheapest reachable fuel stops along the route corridor.
- 🚗 **Vehicle Constraints**:
  - **Max Range**: 500 miles on a full tank.
  - **Fuel Efficiency**: 10 miles per gallon (MPG).
  - Starts the journey with a **full tank**.
- 📊 **Real OPIS Fuel Dataset**: Preprocesses 8,150+ raw records from `fuel-prices-for-be-assessment.csv` into 6,600+ deduplicated, geocoded US stations.
- ⚡ **Blazing Fast Performance (<100ms algorithmic overhead)**: Fuel stations are indexed in a 3D unit-sphere `scipy.spatial.KDTree` at server startup for sub-10ms spatial queries.
- 📡 **Minimal External API Calls (1–3 calls max)**:
  - Exactly **1 call** to the routing API ([OpenRouteService](https://openrouteservice.org/)).
  - **0 to 2 calls** to the geocoding API (skipped completely if coordinates are provided).
  - In-memory caching with 1-hour TTL for instant responses on repeat queries.
- 📖 **Interactive API Documentation**: Auto-generated Swagger UI and ReDoc via `drf-spectacular`.

---

## 🏗️ Architecture & Pipeline Flow

```text
[ Client Request: Start & Finish ]
               │
               ▼
   [ Geocoder Service ]  ── (Cached / Skipped if lat,lon passed)
               │
               ▼
     [ Router Service ]   ── (OpenRouteService Directions API, Cached 1hr)
               │ (Route Polyline & Distance)
               ▼
  [ 3D KD-Tree Corridor Filter ] ── (Find stations within 50 miles of route)
               │
               ▼
   [ Milepost Projection ] ── (Project stations onto route & compute mile markers)
               │
               ▼
   [ Greedy Fuel Optimizer ] ── (Simulate 500-mi range @ 10 MPG, minimize fuel cost)
               │
               ▼
[ Response: Polyline, Interactive Map URL, Fuel Stops, Gallons, & Total Cost ]
```

---

## 🛠️ Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Framework** | Django 4.2 + Django REST Framework | Clean, production-ready web API |
| **API Docs** | `drf-spectacular` | OpenAPI 3.0, Swagger UI, and ReDoc |
| **Routing Engine** | [OpenRouteService API](https://openrouteservice.org/) | Turn-by-turn routing and polyline generation |
| **Spatial Index** | `scipy.spatial.KDTree` + `numpy` | 3D unit-sphere great-circle nearest-neighbor indexing |
| **Data Processing** | `pandas` + `pgeocode` | Offline city/state coordinate resolution and deduplication |
| **Caching** | Django `LocMemCache` | Fast in-memory cache for routing and geocoding responses |

---

## 🏁 Quick Start

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/kipash-prog/spotter-ai.git
cd spotter-ai

# Create and activate virtual environment (optional but recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your free OpenRouteService API key:

```env
ORS_API_KEY=your_actual_openrouteservice_api_key_here
DJANGO_SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

> **Note**: Get a free API key in ~1 minute at [openrouteservice.org/dev/#/signup](https://openrouteservice.org/dev/#/signup).

### 3. Run Migrations & Start Server

```bash
python manage.py migrate
python manage.py runserver
```

The server will load the spatial index of **6,626 fuel stations** into memory and start at `http://localhost:8000/`.

---

## 📖 API Documentation & Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/route/` | Compute optimal fuel route and stops |
| `GET` | `/api/docs/` | Interactive Swagger UI documentation |
| `GET` | `/api/redoc/` | Interactive ReDoc documentation |
| `GET` | `/api/schema/` | Raw OpenAPI 3.0 schema |

---

## 📡 API Reference: `POST /api/v1/route/`

### Request Format

Accepts either city/state names or raw `lat,lon` coordinate strings.

#### Example 1: City & State Names
```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

#### Example 2: Coordinates (Bypasses Geocoding API)
```json
{
  "start": "40.7128,-74.0060",
  "finish": "34.0522,-118.2437"
}
```

---

### Response Format (`200 OK`)

```json
{
  "route": {
    "start": "New York, NY",
    "finish": "Los Angeles, CA",
    "start_lat": 40.7128,
    "start_lon": -74.006,
    "finish_lat": 34.0522,
    "finish_lon": -118.2437,
    "total_distance_miles": 2798.5,
    "estimated_duration_hours": 40.0,
    "route_geometry": [
      [-74.006, 40.7128],
      [-74.015, 40.7135],
      ...
    ],
    "map_url": "https://maps.openrouteservice.org/directions?n1=...&n2=...&b=1a&k1=en-US&k2=km"
  },
  "fuel_stops": [
    {
      "name": "Pilot Flying J #452",
      "address": "4521 Highway Dr",
      "city": "Gary",
      "state": "IN",
      "lat": 41.5934,
      "lon": -87.3465,
      "price_per_gallon": 3.15,
      "distance_from_start_miles": 482.3,
      "gallons_purchased": 48.23,
      "cost_at_this_stop": 151.92
    },
    ...
  ],
  "total_fuel_cost": 839.55,
  "total_gallons": 279.85,
  "vehicle_range_miles": 500,
  "vehicle_mpg": 10
}
```

### Error Responses

| Status Code | Reason | Example Response |
|---|---|---|
| `400 Bad Request` | Missing or invalid fields | `{"start": ["This field is required."]}` |
| `422 Unprocessable Entity` | Geocoding failure or no stations in corridor | `{"error": "Could not geocode location 'InvalidCityXYZ'"}` |
| `502 Bad Gateway` | Upstream ORS routing API error | `{"error": "Routing API error: Rate limit exceeded"}` |
| `503 Service Unavailable` | Fuel station index not loaded | `{"error": "Fuel station index not loaded."}` |

---

## 💡 Algorithm & Optimization Strategy

### 1. Fuel Stop Optimization (Greedy Cost Minimization)

The refueling problem is solved with a provably cost-optimal greedy lookahead strategy:
1. **Initial State**: The vehicle begins at mile `0.0` with a full tank (500 miles of range = 50 gallons @ 10 MPG).
2. **Reachable Horizon**: At the current position, the vehicle can travel up to `current_fuel_range` miles.
3. **Cheaper Station Ahead**:
   - The algorithm scans all candidate stations within reach.
   - If a station with a lower price per gallon exists within range, the vehicle purchases **only enough fuel** to safely reach that cheaper station.
4. **No Cheaper Station Ahead**:
   - If the current station is the cheapest in the reachable window, the vehicle **fills the tank completely** to maximize range bought at the lower price.
5. **Destination Reachable**: If the destination can be reached with the remaining fuel, no further stops are scheduled.

### 2. Spatial Indexing with 3D KD-Tree

To query stations within a 50-mile corridor of routes spanning thousands of miles in milliseconds:
- Latitudes and longitudes are converted to 3D Cartesian unit-sphere coordinates:
  $$x = \cos(\text{lat})\cos(\text{lon}), \quad y = \cos(\text{lat})\sin(\text{lon}), \quad z = \sin(\text{lat})$$
- A `scipy.spatial.KDTree` performs Euclidean chord-distance range queries corresponding to great-circle distances.
- Queries take **< 10ms** across all 6,600+ stations.

---

## 🧪 Running Tests

Run the comprehensive test suite (22 unit and integration tests):

```bash
python manage.py test route_planner
```

### Test Coverage Highlights
- **Haversine Distance**: Symmetry, zero-distance, and cross-country accuracy.
- **Fuel Optimizer**: Zero-stop trips, single mandatory stops, price preference selection, multi-stop cross-country journeys, and tank capacity limits.
- **Geocoder**: Coordinate string parsing, whitespace trimming, and API error handling.
- **Serializers**: Validation of required fields, empty inputs, and identical start/finish points.
- **API Views**: Mocked end-to-end integration tests for success, 400 validation errors, and 422 geocoding failures.

---

## 🐳 Docker Deployment

To build and run the entire application in a Docker container:

```bash
# Build and run with docker-compose
docker-compose up --build
```

The API will be accessible at `http://localhost:8000/api/v1/route/` and Swagger docs at `http://localhost:8000/api/docs/`.

---

## 📂 Project Structure

```text
spotter-ai/
├── config/                     # Django project configuration
│   ├── settings.py             # Settings, ORS config, KD-Tree paths
│   ├── urls.py                 # Root URL routing (API + Swagger + ReDoc)
│   └── wsgi.py                 # WSGI entry point
├── route_planner/              # Core route planning application
│   ├── services/
│   │   ├── fuel_loader.py      # KD-Tree spatial index & station loader
│   │   ├── geocoder.py         # Address geocoding with caching
│   │   ├── router.py           # OpenRouteService directions & map builder
│   │   └── fuel_optimizer.py   # Greedy fuel cost optimization algorithm
│   ├── apps.py                 # AppConfig (initializes KD-Tree at startup)
│   ├── serializers.py          # DRF request & response serializers
│   ├── tests.py                # 22 automated test cases
│   ├── urls.py                 # App URL routing
│   └── views.py                # RoutePlannerView API endpoint
├── data/
│   ├── fuel-prices-for-be-assessment.csv  # Raw Spotter OPIS dataset (8,151 rows)
│   └── fuel_prices.csv                   # Preprocessed & geocoded dataset (6,626 rows)
├── preprocess_fuel_data.py     # Offline geocoding and data cleaning script
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Compose service definition
└── manage.py                   # Django CLI management
```

---
