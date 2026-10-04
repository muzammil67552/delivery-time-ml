"""Routing, Geocoding, and Distance Calculation Engine.

Provides:
1. High-precision Geodesic (Haversine) and urban road-network distance calculations.
2. Preset delivery landmarks and city hubs for hotel operations.
3. Realistic route polyline generation for smooth Leaflet.js map display and courier tracking.
4. Fast fallback routing with optional OSRM highway query.
"""

import math
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional

# Earth radius in kilometers
EARTH_RADIUS_KM = 6371.0

# Standard urban street grid tortuosity/detour factor (road distance / straight-line distance)
URBAN_DETOUR_FACTOR = 1.28

# Pre-configured City Hubs with realistic coordinates and popular delivery landmarks
CITY_PRESETS: Dict[str, Dict[str, Any]] = {
    "New York": {
        "city": "New York, USA",
        "default_lat": 40.7306,
        "default_lng": -73.9866,
        "hotel_address": "Union Square Grand Hotel, East 14th St, New York",
        "landmarks": [
            {"name": "Empire State Commercial Hub", "address": "350 5th Ave", "lat": 40.7484, "lng": -73.9857},
            {"name": "Wall Street Financial District", "address": "11 Wall St", "lat": 40.7069, "lng": -74.0090},
            {"name": "Times Square Entertainment Center", "address": "Broadway & 42nd St", "lat": 40.7580, "lng": -73.9855},
            {"name": "SoHo Fashion Quarter", "address": "Spring St & Broadway", "lat": 40.7223, "lng": -73.9987},
            {"name": "JFK Airport Delivery Hub", "address": "JFK Expressway", "lat": 40.6413, "lng": -73.7781},
            {"name": "Brooklyn Heights Residential", "address": "Montague St", "lat": 40.6960, "lng": -73.9933},
        ],
    },
    "London": {
        "city": "London, UK",
        "default_lat": 51.5074,
        "default_lng": -0.1278,
        "hotel_address": "The Royal Savoy Hotel, Strand, London",
        "landmarks": [
            {"name": "Covent Garden Market Hub", "address": "Covent Garden", "lat": 51.5117, "lng": -0.1232},
            {"name": "City of London Financial Hub", "address": "Bishopsgate", "lat": 51.5155, "lng": -0.0815},
            {"name": "Westminster Government Quarter", "address": "Victoria St", "lat": 51.4995, "lng": -0.1333},
            {"name": "Canary Wharf Tech Dock", "address": "Canada Square", "lat": 51.5050, "lng": -0.0195},
            {"name": "Kensington Residential Park", "address": "Kensington High St", "lat": 51.5014, "lng": -0.1916},
        ],
    },
    "Dubai": {
        "city": "Dubai, UAE",
        "default_lat": 25.1972,
        "default_lng": 55.2744,
        "hotel_address": "Palace Downtown Resort, Sheikh Mohammed bin Rashid Blvd, Dubai",
        "landmarks": [
            {"name": "Burj Khalifa Corporate Tower", "address": "1 Sheikh Mohammed bin Rashid Blvd", "lat": 25.1972, "lng": 55.2744},
            {"name": "Dubai Marina Walk", "address": "Marina Promenade", "lat": 25.0805, "lng": 55.1403},
            {"name": "DIFC Financial Center", "address": "Gate Precinct", "lat": 25.2104, "lng": 55.2818},
            {"name": "Palm Jumeirah Residences", "address": "Crescent Rd", "lat": 25.1124, "lng": 55.1390},
            {"name": "Deira Traditional Souk", "address": "Al Sabkha", "lat": 25.2697, "lng": 55.3095},
        ],
    },
    "San Francisco": {
        "city": "San Francisco, USA",
        "default_lat": 37.7749,
        "default_lng": -122.4194,
        "hotel_address": "Skyline Bay Hotel, Market Street, San Francisco",
        "landmarks": [
            {"name": "Financial District Center", "address": "Montgomery St", "lat": 37.7946, "lng": -122.4025},
            {"name": "Fisherman's Wharf Harbor", "address": "Jefferson St", "lat": 37.8080, "lng": -122.4177},
            {"name": "Mission District Food Hub", "address": "Valencia St", "lat": 37.7600, "lng": -122.4215},
            {"name": "SOMA Tech Campus", "address": "Howard St", "lat": 37.7840, "lng": -122.3990},
            {"name": "Golden Gate Park East", "address": "Stanyan St", "lat": 37.7699, "lng": -122.4533},
        ],
    },
    "Tokyo": {
        "city": "Tokyo, Japan",
        "default_lat": 35.6895,
        "default_lng": 139.6917,
        "hotel_address": "Imperial Grand Shinjuku, Tokyo",
        "landmarks": [
            {"name": "Shinjuku Station Terminal", "address": "Shinjuku 3-Chome", "lat": 35.6909, "lng": 139.7003},
            {"name": "Shibuya Crossing Hub", "address": "Dogenzaka", "lat": 35.6595, "lng": 139.7005},
            {"name": "Roppongi Hills Tower", "address": "Roppongi 6-Chome", "lat": 35.6628, "lng": 139.7291},
            {"name": "Ginza Luxury Avenue", "address": "Ginza 4-Chome", "lat": 35.6719, "lng": 139.7650},
            {"name": "Akihabara Tech Plaza", "address": "Sotokanda", "lat": 35.6983, "lng": 139.7731},
        ],
    },
    "Paris": {
        "city": "Paris, France",
        "default_lat": 48.8566,
        "default_lng": 2.3522,
        "hotel_address": "Grand Hôtel de Paris, Rue de Rivoli, Paris",
        "landmarks": [
            {"name": "Le Marais Historic Quarter", "address": "Rue des Francs-Bourgeois", "lat": 48.8575, "lng": 2.3622},
            {"name": "Champs-Élysées Avenue", "address": "Avenue des Champs-Élysées", "lat": 48.8698, "lng": 2.3078},
            {"name": "Montmartre Artist Village", "address": "Place du Tertre", "lat": 48.8867, "lng": 2.3431},
            {"name": "La Défense Business Center", "address": "Parvis de la Défense", "lat": 48.8924, "lng": 2.2361},
            {"name": "Latin Quarter University Hub", "address": "Boulevard Saint-Michel", "lat": 48.8510, "lng": 2.3438},
        ],
    },
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates straight-line great-circle distance between two GPS coordinates in km."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def estimate_road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Estimates real road driving distance by applying urban detour factors."""
    straight_line = haversine_distance_km(lat1, lon1, lat2, lon2)
    # Apply urban street layout factor; minimum practical distance 0.3 km
    road_dist = straight_line * URBAN_DETOUR_FACTOR
    return max(0.3, round(road_dist, 1))


def generate_curved_waypoints(
    lat1: float, lon1: float, lat2: float, lon2: float, num_points: int = 14
) -> List[List[float]]:
    """Generates intermediate coordinates with realistic street bend simulation.
    
    Produces a smooth polyline connecting origin and destination that looks like
    navigating through urban roads rather than a sterile straight line.
    """
    waypoints: List[List[float]] = []
    
    # Perpendicular offset vector to create a gentle, realistic road curve
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    perp_lat = -d_lon * 0.15
    perp_lon = d_lat * 0.15

    for i in range(num_points + 1):
        t = i / float(num_points)
        # Sine arc offset for curved street effect
        curve_factor = math.sin(t * math.pi)
        
        curr_lat = lat1 + t * d_lat + curve_factor * perp_lat
        curr_lon = lon1 + t * d_lon + curve_factor * perp_lon
        
        waypoints.append([round(curr_lat, 6), round(curr_lon, 6)])

    return waypoints


def calculate_route_navigation(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> Dict[str, Any]:
    """Calculates route distance, estimated transit time, and navigation polyline.
    
    Attempts live OSRM routing with a rapid 1.5s timeout. If unavailable or offline,
    instantly falls back to geodesic detour road calculation and smooth waypoints.
    """
    # Fallback default values
    est_distance = estimate_road_distance_km(origin_lat, origin_lng, dest_lat, dest_lng)
    est_duration = max(3.0, round(est_distance * 2.4, 1))
    waypoints = generate_curved_waypoints(origin_lat, origin_lng, dest_lat, dest_lng)

    # Attempt live OSRM public routing
    osrm_url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{origin_lng:.6f},{origin_lat:.6f};{dest_lng:.6f},{dest_lat:.6f}"
        f"?overview=simplified&geometries=geojson"
    )

    try:
        req = urllib.request.Request(
            osrm_url,
            headers={"User-Agent": "DeliveryTimeML-HotelRouting/1.0"},
        )
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    distance_km = round(route["distance"] / 1000.0, 1)
                    duration_min = round(route["duration"] / 60.0, 1)
                    
                    # OSRM coordinates are in [lng, lat], convert to Leaflet's [lat, lng]
                    geojson_coords = route["geometry"]["coordinates"]
                    leaflet_coords = [[c[1], c[0]] for c in geojson_coords]
                    
                    return {
                        "distance_km": max(0.4, distance_km),
                        "duration_min": max(3.0, duration_min),
                        "route_coords": leaflet_coords,
                        "source": "osrm_live",
                    }
    except Exception:
        # Graceful fallback to urban road physics simulation
        pass

    return {
        "distance_km": est_distance,
        "duration_min": est_duration,
        "route_coords": waypoints,
        "source": "simulated_road_network",
    }
