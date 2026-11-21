from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Satpura / Pachmarhi Area of Interest (AOI)
# Format: [min_lon, min_lat, max_lon, max_lat]
SATPURA_BBOX = [77.90, 22.30, 78.60, 22.70]
PACHMARHI_CENTER = [22.4675, 78.4346]  # [lat, lon] for Folium

# Shared data contract file paths
SCENES_FILE = DATA_DIR / "bhoonidhi_scenes.json"
WEATHER_FUEL_FILE = DATA_DIR / "weather_fuel.json"
CORRIDORS_FILE = DATA_DIR / "corridors.geojson"
ALERTS_ROUTES_FILE = DATA_DIR / "alerts_routes.json"

# Wildfire risk thresholds (0.0 to 1.0)
RISK_THRESHOLDS = {
    "LOW": 0.40,
    "MODERATE": 0.70,
    "CRITICAL": 1.00,
}

# Key Satpura / Pachmarhi monitoring & evacuation nodes
FOREST_NODES = [
    {"name": "Pachmarhi Town", "lat": 22.4675, "lon": 78.4346, "type": "town"},
    {"name": "Madhai Gate", "lat": 22.5890, "lon": 77.9680, "type": "checkpoint"},
    {"name": "Churna Forest Camp", "lat": 22.4780, "lon": 78.0810, "type": "ranger_camp"},
    {"name": "Bori Wildlife Sanctuary", "lat": 22.4120, "lon": 78.2340, "type": "reserve_core"},
    {"name": "Pipariya Base Hub", "lat": 22.7620, "lon": 78.3520, "type": "evacuation_hub"},
]