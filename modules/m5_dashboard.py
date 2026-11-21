import json
import sys
from pathlib import Path

# Ensure root folder (ASTRA/) is on sys.path when launched via `streamlit run modules/m5_dashboard.py`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import config
from modules.m1_satellite_ingest import fetch_bhoonidhi_scenes
from modules.m2_fuel_weather import build_fuel_and_hotspots
from modules.m3_corridor_engine import generate_corridors
from modules.m4_nav_alerts import generate_nav_and_alerts

st.set_page_config(
    page_title="ASTRA | Satpura Wildfire Corridor Tracker",
    page_icon="🛰️",
    layout="wide",
)


def ensure_data_ready():
    if not config.SCENES_FILE.exists():
        fetch_bhoonidhi_scenes()
    if not config.WEATHER_FUEL_FILE.exists():
        build_fuel_and_hotspots()


ensure_data_ready()

with open(config.SCENES_FILE, "r", encoding="utf-8") as f:
    scenes_data = json.load(f)
with open(config.WEATHER_FUEL_FILE, "r", encoding="utf-8") as f:
    wf_data = json.load(f)

base_weather = wf_data["weather"]

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🛰️ ASTRA Mission Control")
st.sidebar.caption("Satpura / Pachmarhi Biosphere Reserve")

scenario = st.sidebar.radio(
    "Weather Scenario",
    ["Live Telemetry", "Dry-Season Storm Demo", "Custom Sliders"],
    index=0,
)

if scenario == "Live Telemetry":
    wind_speed = float(base_weather["wind_speed_kmh"])
    wind_from = float(base_weather["wind_from_deg"])
    humidity = float(base_weather["humidity_pct"])
elif scenario == "Dry-Season Storm Demo":
    wind_speed = 38.0
    wind_from = 245.0  # SW wind pushing corridors straight toward Pachmarhi & Bori
    humidity = 18.0
else:
    wind_speed = st.sidebar.slider("Wind Speed (km/h)", 0.0, 55.0, float(base_weather["wind_speed_kmh"]), 1.0)
    wind_from = st.sidebar.slider("Wind Origin Bearing (°)", 0.0, 359.0, float(base_weather["wind_from_deg"]), 5.0)
    humidity = st.sidebar.slider("Relative Humidity (%)", 10.0, 90.0, float(base_weather["humidity_pct"]), 1.0)

st.sidebar.markdown("---")
st.sidebar.subheader("Map Layers")
show_satellite = st.sidebar.checkbox("ResourceSat-2A Footprints", value=True)
show_corridors = st.sidebar.checkbox("Predicted Fire Corridors", value=True)
show_routes = st.sidebar.checkbox("Safe Evacuation Routes", value=True)
show_nodes = st.sidebar.checkbox("Forest Nodes & Camps", value=True)
basemap_style = st.sidebar.selectbox("Basemap", ["Satellite Imagery", "Terrain / Street"])

if st.sidebar.button("🔄 Refresh Live Satellite & Weather"):
    fetch_bhoonidhi_scenes()
    build_fuel_and_hotspots()
    st.rerun()

# Recompute corridors & navigation live based on active weather parameters
corridors_data = generate_corridors(
    wind_speed_override=wind_speed,
    wind_from_override=wind_from,
    humidity_override=humidity,
    save_output=False,
)
nav_data = generate_nav_and_alerts(corridors_geojson=corridors_data, save_output=False)

# --- HEADER & KPI STRIP ---
st.title("ASTRA — Satpura Wildfire Corridor & Satcom Navigation Tracker")
st.caption(
    f"ISRO Data Backbone: {scenes_data['source']} ({scenes_data['collection']}) | "
    f"Weather Source: {base_weather['source']}"
)

features = corridors_data["features"]
total_area = round(sum(f["properties"]["approx_area_km2"] for f in features), 2)
spread_bearing = corridors_data["metadata"]["spread_bearing_deg"]
critical_count = sum(1 for f in features if f["properties"]["risk_level"] == "CRITICAL")
latest_scene = scenes_data["scenes"][0] if scenes_data["scenes"] else {}

k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Thermal Hotspots", len(features), f"{critical_count} Critical")
k2.metric("Projected Spread Area", f"{total_area} km²", f"Wind {wind_speed:.1f} km/h")
k3.metric("Downwind Fire Vector", f"{spread_bearing:.0f}°", f"Humidity {humidity:.0f}%")
cloud_val = latest_scene.get("cloud_cover")
cloud_label = f"Cloud {cloud_val}%" if cloud_val is not None else f"{scenes_data['scene_count']} Live Scenes"
k4.metric("Latest ResourceSat-2A Pass", str(latest_scene.get("datetime", "N/A"))[:10], cloud_label)

# --- INTERACTIVE FOLIUM MAP ---
tiles = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    if basemap_style == "Satellite Imagery"
    else "OpenStreetMap"
)
attr = "Esri World Imagery" if basemap_style == "Satellite Imagery" else "OpenStreetMap"

m = folium.Map(location=config.PACHMARHI_CENTER, zoom_start=11, tiles=tiles, attr=attr)

# 1. ResourceSat-2A Footprints
if show_satellite:
    for sc in scenes_data.get("scenes", [])[:2]:
        if sc.get("geometry"):
            folium.GeoJson(
                sc["geometry"],
                name=f"Scene {sc['id']}",
                style_function=lambda _: {
                    "color": "#38bdf8",
                    "weight": 2,
                    "dashArray": "6, 6",
                    "fillOpacity": 0.04,
                },
                tooltip=f"ResourceSat-2A | {sc['id']} | Pass: {str(sc.get('datetime', 'N/A'))[:10]}",
            ).add_to(m)

# 2. Predicted Fire Corridors & Hotspot Origins
risk_colors = {"CRITICAL": "#ef4444", "MODERATE": "#f59e0b", "LOW": "#eab308"}
if show_corridors:
    for feat in features:
        props = feat["properties"]
        color = risk_colors.get(props["risk_level"], "#f59e0b")

        folium.GeoJson(
            feat,
            style_function=lambda _, c=color: {
                "color": c,
                "weight": 2,
                "fillColor": c,
                "fillOpacity": 0.38,
            },
            tooltip=(
                f"<b>{props['hotspot_id']} — {props['sector']}</b><br>"
                f"Risk: {props['risk_level']} ({props['risk_score']})<br>"
                f"6h Spread: {props['projected_spread_km']} km @ {props['spread_bearing_deg']}°<br>"
                f"Area: {props['approx_area_km2']} km²"
            ),
        ).add_to(m)

        folium.CircleMarker(
            location=[props["origin_lat"], props["origin_lon"]],
            radius=7,
            color="#ffffff",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=1.0,
            popup=f"Ignition Hotspot: {props['hotspot_id']} ({props['sector']})",
        ).add_to(m)

# 3. Safe Evacuation Routes
if show_routes:
    for r in nav_data["evacuation_routes"]:
        folium.PolyLine(
            locations=r["waypoints_latlon"],
            color="#22c55e",
            weight=4,
            dash_array="8, 6",
            tooltip=(
                f"Safe Route: {r['from_node']} → {r['to_hub']} "
                f"({r['distance_km']} km | Flank Exit: {r['exit_bearing_deg']}°)"
            ),
        ).add_to(m)

# 4. Forest Nodes & Evacuation Hubs
status_colors = {"EVACUATE": "red", "ALERT": "orange", "WATCH": "beige", "SAFE": "green"}
if show_nodes:
    for node in nav_data["node_assessments"]:
        folium.Marker(
            location=[node["lat"], node["lon"]],
            icon=folium.Icon(color=status_colors.get(node["status"], "blue"), icon="info-sign"),
            tooltip=f"{node['name']} [{node['status']}] — {node['distance_to_fire_km']} km from nearest hotspot",
        ).add_to(m)

st_folium(m, width=None, height=520, returned_objects=[])

# --- BOTTOM TELEMETRY PANELS ---
tab1, tab2, tab3 = st.tabs(["📡 Satcom Ranger Alerts", "🧭 Forest Node Status & Routes", "🛰️ Bhoonidhi Scene Metadata"])

with tab1:
    alerts = nav_data["satcom_alerts"]
    if alerts:
        st.dataframe(pd.DataFrame(alerts), width="stretch", hide_index=True)
    else:
        st.success("All monitored forest nodes are currently outside immediate evacuation corridors.")

with tab2:
    st.dataframe(pd.DataFrame(nav_data["node_assessments"]), width="stretch", hide_index=True)

with tab3:
    scene_rows = [
        {
            "Scene ID": s.get("id"),
            "Acquisition UTC": s.get("datetime"),
            "Cloud Cover (%)": s.get("cloud_cover"),
            "BBox": str(s.get("bbox")),
        }
        for s in scenes_data.get("scenes", [])
    ]
    st.dataframe(pd.DataFrame(scene_rows), width="stretch", hide_index=True)