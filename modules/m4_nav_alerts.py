import json
import math
from datetime import datetime, timezone
import config


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return round((math.degrees(math.atan2(y, x)) + 360.0) % 360.0, 1)


def _point_in_polygon(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting check using GeoJSON [lon, lat] polygon ring."""
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if ((y1 > lat) != (y2 > lat)) and (
            lon < (x2 - x1) * (lat - y1) / ((y2 - y1) + 1e-12) + x1
        ):
            inside = not inside
    return inside


def _offset_latlon(lat: float, lon: float, dist_km: float, bearing: float) -> list[float]:
    rad = math.radians(bearing)
    d_lat = (dist_km * math.cos(rad)) / 111.32
    d_lon = (dist_km * math.sin(rad)) / (111.32 * math.cos(math.radians(lat)))
    return [round(lat + d_lat, 5), round(lon + d_lon, 5)]


def generate_nav_and_alerts(
    corridors_geojson: dict | None = None,
    save_output: bool = True,
) -> dict:
    """Evaluates node threats, computes safe evacuation routes, and builds satcom alerts."""
    if corridors_geojson is None:
        with open(config.CORRIDORS_FILE, "r", encoding="utf-8") as f:
            corridors_geojson = json.load(f)

    features = corridors_geojson.get("features", [])
    spread_bearing = corridors_geojson.get("metadata", {}).get("spread_bearing_deg", 60.0)

    evacuation_hubs = [n for n in config.FOREST_NODES if n["type"] in ("evacuation_hub", "checkpoint")]
    node_assessments = []
    routes = []
    satcom_alerts = []

    for node in config.FOREST_NODES:
        n_lat, n_lon = node["lat"], node["lon"]
        nearest_dist = 999.0
        nearest_hotspot = None
        inside_corridor = False
        max_threat_risk = "LOW"

        for feat in features:
            props = feat["properties"]
            ring = feat["geometry"]["coordinates"][0]
            dist = _haversine_km(n_lat, n_lon, props["origin_lat"], props["origin_lon"])

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_hotspot = props["hotspot_id"]

            if _point_in_polygon(n_lon, n_lat, ring):
                inside_corridor = True
                max_threat_risk = props["risk_level"]

        if inside_corridor:
            status = "EVACUATE"
        elif nearest_dist <= 9.0:
            status = "EVACUATE" if max_threat_risk == "CRITICAL" else "ALERT"
        elif nearest_dist <= 16.0:
            status = "WATCH"
        else:
            status = "SAFE"

        # Determine safe exit route for any non-SAFE node
        exit_bearing = round((spread_bearing + 90.0) % 360.0, 1)  # Perpendicular flank escape
        safe_hub = min(
            [h for h in evacuation_hubs if h["name"] != node["name"]] or evacuation_hubs,
            key=lambda h: _haversine_km(n_lat, n_lon, h["lat"], h["lon"]),
        )

        if status in ("EVACUATE", "ALERT"):
            flank_waypoint = _offset_latlon(n_lat, n_lon, 4.0, exit_bearing)
            route_coords = [
                [n_lat, n_lon],
                flank_waypoint,
                [safe_hub["lat"], safe_hub["lon"]],
            ]
            hub_dist = _haversine_km(n_lat, n_lon, safe_hub["lat"], safe_hub["lon"])
            hub_bearing = _bearing_deg(n_lat, n_lon, safe_hub["lat"], safe_hub["lon"])

            routes.append(
                {
                    "from_node": node["name"],
                    "to_hub": safe_hub["name"],
                    "priority": status,
                    "distance_km": hub_dist,
                    "exit_bearing_deg": exit_bearing,
                    "hub_bearing_deg": hub_bearing,
                    "waypoints_latlon": route_coords,
                }
            )

            # Compact satcom uplink string (designed for S-band / NavIC short-burst messaging)
            compact_msg = (
                f"ASTRA|{status}|{node['name'][:12].upper()}|"
                f"POS:{n_lat:.3f},{n_lon:.3f}|HS:{nearest_hotspot}|"
                f"EXIT:{exit_bearing:.0f}DEG->HUB:{safe_hub['name'][:10].upper()}"
            )
            satcom_alerts.append(
                {
                    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "severity": status,
                    "node": node["name"],
                    "nearest_hotspot": nearest_hotspot,
                    "distance_km": nearest_dist,
                    "recommended_hub": safe_hub["name"],
                    "exit_bearing_deg": exit_bearing,
                    "satcom_payload": compact_msg,
                    "payload_bytes": len(compact_msg.encode("utf-8")),
                }
            )

        node_assessments.append(
            {
                "name": node["name"],
                "type": node["type"],
                "lat": n_lat,
                "lon": n_lon,
                "status": status,
                "inside_corridor": inside_corridor,
                "nearest_hotspot": nearest_hotspot,
                "distance_to_fire_km": nearest_dist,
            }
        )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node_assessments": node_assessments,
        "evacuation_routes": routes,
        "satcom_alerts": satcom_alerts,
    }

    if save_output:
        with open(config.ALERTS_ROUTES_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(
            f"[Module 4] Assessed {len(node_assessments)} nodes | "
            f"{len(routes)} safe routes | {len(satcom_alerts)} satcom alerts -> {config.ALERTS_ROUTES_FILE}"
        )

    return output


if __name__ == "__main__":
    res = generate_nav_and_alerts()
    for a in res["satcom_alerts"]:
        print(f"  [{a['severity']}] ({a['payload_bytes']}B) {a['satcom_payload']}")