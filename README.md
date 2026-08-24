# Spotter AI — Route Planner API

A Django REST API that computes the optimal fuel stop plan for any US road trip, minimizing total fuel cost.

## Features

- 🗺️ **Full route planning** — accepts any US start/finish location (city names or `lat,lon`)
- ⛽ **Cost-optimal fuel stops** — greedy algorithm that minimizes total fuel spend
- 🚗 **500-mile range vehicle** with 10 mpg fuel economy
- ⚡ **Fast responses** — fuel data is indexed in a KD-Tree at startup; external API calls are cached
- 📡 **Minimal API calls** — at most 1 routing call + 2 geocoding calls per unique route

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | Django 4.2 + Django REST Framework |
| Routing API | [OpenRouteService](https://openrouteservice.org/) (free tier) |
| Geocoding | OpenRouteService Geocoding API |
| Spatial Index | `scipy.spatial.KDTree` |
| Caching | Django in-memory cache |
| Data | 487 US fuel stations with realistic prices |

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <your-repo-url>
cd spotter-ai
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your ORS_API_KEY
```

Get a free API key at [openrouteservice.org](https://openrouteservice.org/) (takes ~1 minute).

### 3. Run migrations & start server

```bash
python manage.py migrate
python manage.py runserver
```

The API is now available at `http://localhost:8000/api/v1/route/`

---

## API Reference

### `POST /api/v1/route/`

Plan an optimal fuel route between two US locations.

**Request Body**

```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

You can also use raw coordinates:

```json
{
  "start": "40.7128,-74.0060",
  "finish": "34.0522,-118.2437"
}
```

**Response**

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
    "route_geometry": [[-74.006, 40.7128], ...],
    "map_url": "https://maps.openrouteservice.org/directions?..."
  },
  "fuel_stops": [
    {
      "name": "Pilot Flying J",
      "address": "4521 Highway Dr, Gary, IN",
      "city": "Gary",
      "state": "IN",
      "lat": 41.5934,
      "lon": -87.3465,
      "price_per_gallon": 3.15,
      "distance_from_start_miles": 790.2,
      "gallons_purchased": 35.4,
      "cost_at_this_stop": 111.51
    }
  ],
  "total_fuel_cost": 839.55,
  "total_gallons": 261.98,
  "vehicle_range_miles": 500,
  "vehicle_mpg": 10
}
```

**Error Responses**

| Status | Meaning |
|--------|---------|
| `400` | Missing/invalid input fields |
| `422` | Location could not be geocoded |
| `502` | Routing API call failed |
| `503` | Fuel station index not loaded |

---

## Algorithm

### Fuel Stop Optimization

The optimizer uses a **greedy cost-minimization** strategy:

1. Start at mile 0 with a **full tank** (500 miles of fuel)
2. At each position, scan all stations within the next 500 miles
3. If a **cheaper station** exists within range → buy just enough fuel to reach it
4. If no cheaper station is ahead → **fill the tank completely** at the cheapest reachable station
5. Repeat until the destination is within range

This greedy approach is provably optimal for single-commodity refueling problems.

### Spatial Indexing

Fuel stations are pre-indexed into a `scipy.spatial.KDTree` at server startup using 3-D unit-sphere coordinates for accurate great-circle distance queries. Station lookup for any route takes < 10ms regardless of dataset size.

### Milepost Assignment

Each candidate station is projected onto the route polyline by finding its closest point, computing the cumulative distance from the start. This runs in O(P × S) where P = polyline points and S = nearby stations.

---

## Running Tests

```bash
python manage.py test route_planner
```

Test coverage includes:
- Haversine distance calculation
- Optimizer: no-stop trip, single mandatory stop, cost preference, multi-stop
- Geocoder: coordinate passthrough, missing API key
- Serializer: validation rules
- API: success, missing fields, geocoder errors (all mocked)

---

## Docker

```bash
# Build and run
docker-compose up --build

# API available at http://localhost:8000/api/v1/route/
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ORS_API_KEY` | OpenRouteService API key | — (required) |
| `DJANGO_SECRET_KEY` | Django secret key | fallback (change in prod!) |
| `DEBUG` | Enable debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated list | `localhost,127.0.0.1` |

---

## Project Structure

```
spotter-ai/
├── config/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── route_planner/          # Main Django app
│   ├── services/
│   │   ├── fuel_loader.py  # CSV → KD-Tree index
│   │   ├── geocoder.py     # Address → coordinates
│   │   ├── router.py       # ORS directions API
│   │   └── fuel_optimizer.py  # Greedy stop selector
│   ├── views.py            # API endpoint
│   ├── serializers.py      # Request/response validation
│   ├── urls.py
│   └── tests.py
├── data/
│   └── fuel_prices.csv     # 487 US fuel stations
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── manage.py
```
