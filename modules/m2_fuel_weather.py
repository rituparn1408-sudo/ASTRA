import json
from datetime import datetime, timezone
import requests
import config


def fetch_live_weather(lat: float, lon: float) -> dict:
    """Fetches current wind & humidity telemetry; falls back cleanly if offline."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        cur = resp.json().get("current", {})
        return {
            "source": "Live Weather Telemetry (MOSDAC-compatible schema)",
            "temperature_c": float(cur.get("temperature_2m", 34.5)),
            "humidity_pct": float(cur.get("relative_humidity_2m", 28.0)),
            "wind_speed_kmh": float(cur.get("wind_speed_10m", 18.0)),
            "wind_from_deg": float(cur.get("wind_direction_10m", 245.0)),
        }
    except requests.RequestException as exc:
        print(f"[Module 2] Live weather unavailable ({exc}); using Satpura dry-season baseline.")
        return {
            "source": "Satpura Dry-Season Baseline (Offline Fallback)",
            "temperature_c": 36.2,
            "humidity_pct": 24.0,
            "wind_speed_kmh": 22.0,
            "wind_from_deg": 240.0,  # Blowing from SW towards NE (Pachmarhi ridge)
        }


def build_fuel_and_hotspots() -> dict:
    """Combines weather physics, VEDAS-style NDVI dryness, and thermal hotspots."""
    lat, lon = config.PACHMARHI_CENTER
    weather = fetch_live_weather(lat, lon)

    # Sector hotspots & fuel dryness (0.0 = wet green canopy, 1.0 = bone-dry fuel)
    hotspots = [
        {
            "hotspot_id": "SAT-HS-01",
            "sector": "Bori-Churna Dry Corridor",
            "lat": 22.4350,
            "lon": 78.1450,
            "brightness_k": 342.5,
            "ndvi": 0.24,
            "fuel_dryness": 0.84,
            "confidence": "HIGH",
        },
        {
            "hotspot_id": "SAT-HS-02",
            "sector": "Southwest Pachmarhi Escarpment",
            "lat": 22.4480,
            "lon": 78.3620,
            "brightness_k": 336.1,
            "ndvi": 0.31,
            "fuel_dryness": 0.76,
            "confidence": "HIGH",
        },
        {
            "hotspot_id": "SAT-HS-03",
            "sector": "Madhai Buffer Belt",
            "lat": 22.5520,
            "lon": 77.9950,
            "brightness_k": 318.4,
            "ndvi": 0.48,
            "fuel_dryness": 0.52,
            "confidence": "MEDIUM",
        },
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aoi_bbox": config.SATPURA_BBOX,
        "weather": weather,
        "hotspots": hotspots,
    }

    with open(config.WEATHER_FUEL_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(
        f"[Module 2] Saved weather ({weather['wind_speed_kmh']} km/h @ "
        f"{weather['wind_from_deg']} deg) & {len(hotspots)} hotspots -> {config.WEATHER_FUEL_FILE}"
    )
    return payload


if __name__ == "__main__":
    build_fuel_and_hotspots()