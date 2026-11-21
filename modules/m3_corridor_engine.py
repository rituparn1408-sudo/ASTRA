import json
import math
from datetime import datetime, timezone
import config


def _offset_point(lat: float, lon: float, distance_km: float, bearing_deg: float) -> list[float]:
    """Returns [lon, lat] (GeoJSON order) offset by distance_km along a compass bearing."""
    bearing_rad = math.radians(bearing_deg)
    d_lat = (distance_km * math.cos(bearing_rad)) / 111.32
    d_lon = (distance_km * math.sin(bearing_rad)) / (111.32 * math.cos(math.radians(lat)))
    return [round(lon + d_lon, 5), round(lat + d_lat, 5)]


def _classify_risk(score: float) -> str:
    if score < config.RISK_THRESHOLDS["LOW"]:
        return "LOW"
    if score < config.RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "CRITICAL"


def compute_risk_score(fuel_dryness: float, wind_speed_kmh: float, humidity_pct: float) -> float:
    """Weighted wildfire risk formula normalized to [0.0, 1.0]."""
    wind_factor = min(max(wind_speed_kmh, 0.0) / 45.0, 1.0)
    low_humidity = min(max((100.0 - humidity_pct) / 100.0, 0.0), 1.0)
    score = (0.45 * fuel_dryness) + (0.35 * wind_factor) + (0.20 * low_humidity)
    return round(min(max(score, 0.0), 1.0), 3)


def _build_corridor_polygon(
    lat: float,
    lon: float,
    spread_bearing_deg: float,
    length_km: float,
    half_angle_deg: float = 22.0,
) -> dict:
    """Generates a downwind fan/corridor polygon in GeoJSON [lon, lat] coordinates."""
    origin = [round(lon, 5), round(lat, 5)]
    left_flank = _offset_point(lat, lon, length_km * 0.65, (spread_bearing_deg - half_angle_deg) % 360)
    tip_left = _offset_point(lat, lon, length_km * 0.95, (spread_bearing_deg - half_angle_deg * 0.45) % 360)
    tip_center = _offset_point(lat, lon, length_km, spread_bearing_deg)
    tip_right = _offset_point(lat, lon, length_km * 0.95, (spread_bearing_deg + half_angle_deg * 0.45) % 360)
    right_flank = _offset_point(lat, lon, length_km * 0.65, (spread_bearing_deg + half_angle_deg) % 360)

    ring = [origin, left_flank, tip_left, tip_center, tip_right, right_flank, origin]
    return {"type": "Polygon", "coordinates": [ring]}


def generate_corridors(
    wind_speed_override: float | None = None,
    wind_from_override: float | None = None,
    humidity_override: float | None = None,
    save_output: bool = True,
) -> dict:
    """Reads weather_fuel.json and outputs predicted wildfire spread corridors as GeoJSON."""
    with open(config.WEATHER_FUEL_FILE, "r", encoding="utf-8") as f:
        wf_data = json.load(f)

    weather = wf_data["weather"]
    wind_speed = wind_speed_override if wind_speed_override is not None else weather["wind_speed_kmh"]
    wind_from = wind_from_override if wind_from_override is not None else weather["wind_from_deg"]
    humidity = humidity_override if humidity_override is not None else weather["humidity_pct"]

    # Fire spreads downwind (opposite of wind origin bearing)
    spread_bearing = round((wind_from + 180.0) % 360.0, 1)

    features = []
    for hs in wf_data["hotspots"]:
        risk_score = compute_risk_score(hs["fuel_dryness"], wind_speed, humidity)
        risk_level = _classify_risk(risk_score)

        # Projected 6-hour spread distance scales with wind speed and fuel dryness
        spread_km = round(2.5 + (wind_speed * 0.28 * hs["fuel_dryness"]), 2)
        approx_area_km2 = round(0.5 * (spread_km ** 2) * math.radians(44.0), 2)

        polygon = _build_corridor_polygon(hs["lat"], hs["lon"], spread_bearing, spread_km)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "hotspot_id": hs["hotspot_id"],
                    "sector": hs["sector"],
                    "origin_lat": hs["lat"],
                    "origin_lon": hs["lon"],
                    "fuel_dryness": hs["fuel_dryness"],
                    "wind_speed_kmh": wind_speed,
                    "wind_from_deg": wind_from,
                    "spread_bearing_deg": spread_bearing,
                    "projected_spread_km": spread_km,
                    "approx_area_km2": approx_area_km2,
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                },
                "geometry": polygon,
            }
        )

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "wind_speed_kmh": wind_speed,
            "wind_from_deg": wind_from,
            "spread_bearing_deg": spread_bearing,
            "humidity_pct": humidity,
        },
        "features": features,
    }

    if save_output:
        with open(config.CORRIDORS_FILE, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        print(f"[Module 3] Generated {len(features)} fire corridors -> {config.CORRIDORS_FILE}")

    return geojson


if __name__ == "__main__":
    result = generate_corridors()
    for feat in result["features"]:
        p = feat["properties"]
        print(
            f"  - {p['hotspot_id']} ({p['sector']}): "
            f"Risk={p['risk_score']} [{p['risk_level']}], "
            f"Spread={p['projected_spread_km']} km @ {p['spread_bearing_deg']} deg"
        )