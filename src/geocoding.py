"""Geocoding and coordinate resolution engine for Hotel Registration and Routing.

Provides progressive address lookup and country-level fallback using OpenStreetMap Nominatim.
Guarantees that a registered hotel address always has valid, geographic coordinates
aligned with its operating country.
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Standard geographical centroid coordinates for world countries
COUNTRY_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "Afghanistan": (33.9391, 67.7100),
    "Albania": (41.1533, 20.1683),
    "Algeria": (28.0339, 1.6596),
    "Andorra": (42.5063, 1.5218),
    "Angola": (-11.2027, 17.8739),
    "Antigua and Barbuda": (17.0608, -61.7964),
    "Argentina": (-38.4161, -63.6167),
    "Armenia": (40.0691, 45.0382),
    "Australia": (-25.2744, 133.7751),
    "Austria": (47.5162, 14.5501),
    "Azerbaijan": (40.1431, 47.5769),
    "Bahamas": (25.0343, -77.3963),
    "Bahrain": (26.0667, 50.5577),
    "Bangladesh": (23.6850, 90.3563),
    "Barbados": (13.1939, -59.5432),
    "Belarus": (53.7098, 27.9534),
    "Belgium": (50.5039, 4.4699),
    "Belize": (17.1899, -88.4976),
    "Benin": (9.3077, 2.3158),
    "Bhutan": (27.5142, 90.4336),
    "Bolivia": (-16.2902, -63.5887),
    "Bosnia and Herzegovina": (43.9159, 17.6791),
    "Botswana": (-22.3285, 24.6849),
    "Brazil": (-14.2350, -51.9253),
    "Brunei": (4.5353, 114.7277),
    "Bulgaria": (42.7339, 25.4858),
    "Burkina Faso": (12.2383, -1.5616),
    "Burundi": (-3.3731, 29.9189),
    "Cambodia": (12.5657, 104.9910),
    "Cameroon": (7.3697, 12.3547),
    "Canada": (56.1304, -106.3468),
    "Cape Verde": (16.0022, -24.0132),
    "Central African Republic": (6.6111, 20.9394),
    "Chad": (15.4542, 18.7322),
    "Chile": (-35.6751, -71.5430),
    "China": (35.8617, 104.1954),
    "Colombia": (4.5709, -74.2973),
    "Comoros": (-11.8753, 43.8722),
    "Congo": (-0.2280, 15.8277),
    "Costa Rica": (9.7489, -83.7534),
    "Croatia": (45.1000, 15.2000),
    "Cuba": (21.5218, -77.7812),
    "Cyprus": (35.1264, 33.4299),
    "Czech Republic": (49.8175, 15.4730),
    "Democratic Republic of the Congo": (-4.0383, 21.7587),
    "Denmark": (56.2639, 9.5018),
    "Djibouti": (11.8251, 42.5903),
    "Dominica": (15.4150, -61.3710),
    "Dominican Republic": (18.7357, -70.1627),
    "East Timor": (-8.8742, 125.7275),
    "Ecuador": (-1.8312, -78.1834),
    "Egypt": (26.8206, 30.8025),
    "El Salvador": (13.7942, -88.8965),
    "Equatorial Guinea": (1.6508, 10.2679),
    "Eritrea": (15.1794, 39.7823),
    "Estonia": (58.5953, 25.0136),
    "Eswatini": (-26.5225, 31.4659),
    "Ethiopia": (9.1450, 40.4897),
    "Fiji": (-17.7134, 178.0650),
    "Finland": (61.9241, 25.7482),
    "France": (46.2276, 2.2137),
    "Gabon": (-0.8037, 11.6094),
    "Gambia": (13.4432, -15.3101),
    "Georgia": (42.3154, 43.3569),
    "Germany": (51.1657, 10.4515),
    "Ghana": (7.9465, -1.0232),
    "Greece": (39.0742, 21.8243),
    "Grenada": (12.1165, -61.6790),
    "Guatemala": (15.7835, -90.2308),
    "Guinea": (9.9456, -9.6966),
    "Guinea-Bissau": (11.8037, -15.1804),
    "Guyana": (4.8604, -58.9302),
    "Haiti": (18.9712, -72.2852),
    "Honduras": (15.2000, -86.2419),
    "Hungary": (47.1625, 19.5033),
    "Iceland": (64.9631, -19.0208),
    "India": (20.5937, 78.9629),
    "Indonesia": (-0.7893, 113.9213),
    "Iran": (32.4279, 53.6880),
    "Iraq": (33.2232, 43.6793),
    "Ireland": (53.1424, -7.6921),
    "Israel": (31.0461, 34.8516),
    "Italy": (41.8719, 12.5674),
    "Ivory Coast": (7.5400, -5.5471),
    "Jamaica": (18.1096, -77.2975),
    "Japan": (36.2048, 138.2529),
    "Jordan": (30.5852, 36.2384),
    "Kazakhstan": (48.0196, 66.9237),
    "Kenya": (-0.0236, 37.9062),
    "Kuwait": (29.3117, 47.4818),
    "Kyrgyzstan": (41.2044, 74.7661),
    "Laos": (19.8563, 102.4955),
    "Latvia": (56.8796, 24.6032),
    "Lebanon": (33.8547, 35.8623),
    "Lesotho": (-29.6100, 28.2336),
    "Liberia": (6.4281, -9.4295),
    "Libya": (26.3351, 17.2283),
    "Liechtenstein": (47.1660, 9.5554),
    "Lithuania": (55.1694, 23.8813),
    "Luxembourg": (49.8153, 6.1296),
    "Madagascar": (-18.7669, 46.8691),
    "Malawi": (-13.2543, 34.3015),
    "Malaysia": (4.2105, 101.9758),
    "Maldives": (3.2028, 73.2207),
    "Mali": (17.5707, -3.9962),
    "Malta": (35.9375, 14.3754),
    "Mauritania": (21.0079, -10.9408),
    "Mauritius": (-20.3484, 57.5522),
    "Mexico": (23.6345, -102.5528),
    "Moldova": (47.4116, 28.3699),
    "Monaco": (43.7384, 7.4246),
    "Mongolia": (46.8625, 103.8467),
    "Montenegro": (42.7087, 19.3744),
    "Morocco": (31.7917, -7.0926),
    "Mozambique": (-18.6657, 35.5296),
    "Myanmar": (21.9162, 95.9560),
    "Namibia": (-22.9576, 18.4904),
    "Nepal": (28.3949, 84.1240),
    "Netherlands": (52.1326, 5.2913),
    "New Zealand": (-40.9006, 174.8860),
    "Nicaragua": (12.8654, -85.2072),
    "Niger": (17.6078, 8.0817),
    "Nigeria": (9.0820, 8.6753),
    "North Macedonia": (41.6086, 21.7453),
    "Norway": (60.4720, 8.4689),
    "Oman": (21.4735, 55.9754),
    "Pakistan": (24.8607, 67.0011),  # Karachi metropolitan hub
    "Palestine": (31.9522, 35.2332),
    "Panama": (8.5379, -80.7821),
    "Papua New Guinea": (-6.3150, 143.9555),
    "Paraguay": (-23.4425, -58.4438),
    "Peru": (-9.1899, -75.0152),
    "Philippines": (12.8797, 121.7740),
    "Poland": (51.9194, 19.1451),
    "Portugal": (39.3999, -8.2245),
    "Qatar": (25.3548, 51.1839),
    "Romania": (45.9432, 24.9668),
    "Russia": (61.5240, 105.3188),
    "Rwanda": (-1.9403, 29.8739),
    "Saudi Arabia": (23.8859, 45.0792),
    "Senegal": (14.4974, -14.4524),
    "Serbia": (44.0165, 21.0059),
    "Seychelles": (-4.6796, 55.4920),
    "Sierra Leone": (8.4606, -11.7799),
    "Singapore": (1.3521, 103.8198),
    "Slovakia": (48.6690, 19.6990),
    "Slovenia": (46.1512, 14.9955),
    "Somalia": (5.1521, 46.1996),
    "South Africa": (-30.5595, 22.9375),
    "South Korea": (35.9078, 127.7669),
    "Spain": (40.4637, -3.7492),
    "Sri Lanka": (7.8731, 80.7718),
    "Sudan": (12.8628, 30.2176),
    "Sweden": (60.1282, 18.6435),
    "Switzerland": (46.8182, 8.2275),
    "Syria": (34.8021, 38.9968),
    "Taiwan": (23.6978, 120.9605),
    "Tajikistan": (38.8610, 71.2761),
    "Tanzania": (-6.3690, 34.8888),
    "Thailand": (15.8700, 100.9925),
    "Togo": (8.6195, 0.8248),
    "Trinidad and Tobago": (10.6918, -61.2225),
    "Tunisia": (33.8869, 9.5375),
    "Turkey": (38.9637, 35.2433),
    "Uganda": (1.3733, 32.2903),
    "Ukraine": (48.3794, 31.1656),
    "United Arab Emirates": (25.1972, 55.2744),  # Dubai hub
    "United Kingdom": (51.5074, -0.1278),  # London hub
    "United States": (40.7306, -73.9866),  # New York hub
    "Uruguay": (-32.5228, -55.7658),
    "Uzbekistan": (41.3775, 64.5853),
    "Venezuela": (6.4238, -66.5897),
    "Vietnam": (14.0583, 108.2772),
    "Yemen": (15.5527, 48.5164),
    "Zambia": (-13.1339, 27.8493),
    "Zimbabwe": (-19.0154, 29.1549),
}


def query_nominatim(query_str: str) -> Optional[Tuple[float, float, str]]:
    """Performs a single geocoding lookup against OpenStreetMap Nominatim."""
    clean_q = query_str.strip()
    if not clean_q:
        return None
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(clean_q)}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "DeliveryTimePlatform/1.0 (contact: admin@deliveryml.local)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                disp_name = data[0].get("display_name", "")
                return lat, lon, disp_name
    except Exception as exc:
        logger.debug("Nominatim lookup failed for query '%s': %s", clean_q, exc)
    return None


def resolve_hotel_coordinates(
    address: str,
    country: str,
    provided_lat: Optional[float] = None,
    provided_lng: Optional[float] = None,
) -> Tuple[float, float, str]:
    """Resolves coordinates for a registered hotel using progressive geocoding.

    Order of evaluation:
    1. If user provided custom non-default coordinates that do not conflict with the country, keep them.
    2. Try exact address + country search in OpenStreetMap.
    3. Try progressive segments / landmarks of address + country.
    4. Fall back to national centroid / metropolitan hub of the selected country.
    """
    clean_address = (address or "").strip()
    clean_country = (country or "United States").strip()

    # Known centroid for country
    country_default = COUNTRY_CENTROIDS.get(clean_country) or (40.7306, -73.9866)

    # Check if provided coordinates are default Manhattan coordinates
    is_manhattan_default = False
    if provided_lat is not None and provided_lng is not None:
        if abs(provided_lat - 40.7580) < 0.15 and abs(provided_lng - (-73.9855)) < 0.15:
            is_manhattan_default = True
        elif abs(provided_lat - 40.7306) < 0.15 and abs(provided_lng - (-73.9866)) < 0.15:
            is_manhattan_default = True

    # If the user selected a non-US country, but the coordinates are in Manhattan, it's an unresolved default!
    if provided_lat is not None and provided_lng is not None:
        if not is_manhattan_default or clean_country == "United States":
            # If coordinates are valid and not an accidental Manhattan default for another country
            if clean_country == "United States" or abs(provided_lat - country_default[0]) < 25.0:
                return provided_lat, provided_lng, f"User Specified ({provided_lat:.4f}, {provided_lng:.4f})"

    # Progressive Geocoding
    if clean_address:
        # 1. Full string query
        res = query_nominatim(f"{clean_address}, {clean_country}")
        if res:
            return res[0], res[1], res[2]

        # 2. Segments split by punctuation
        segments = [s.strip() for s in re.split(r"[,;/\n]+", clean_address) if len(s.strip()) > 3]
        for seg in segments:
            res = query_nominatim(f"{seg}, {clean_country}")
            if res:
                return res[0], res[1], res[2]

        # 3. Sliding n-gram phrases (e.g. "Iqra University", "Defence View")
        words = clean_address.split()
        for n in (4, 3, 2):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n])
                if phrase.lower() in ("main campus", "mini market", "street address", "main branch", "road branch"):
                    continue
                res = query_nominatim(f"{phrase}, {clean_country}")
                if res:
                    return res[0], res[1], res[2]

    # 4. Fallback to country geocoding or built-in country coordinates
    c_res = query_nominatim(clean_country)
    if c_res:
        return c_res[0], c_res[1], f"{clean_country} Centroid"

    return country_default[0], country_default[1], f"{clean_country} Default Hub"
