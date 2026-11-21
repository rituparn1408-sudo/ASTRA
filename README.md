# ASTRA — Satpura Wildfire Corridor & Satcom Navigation Tracker

A modular wildfire prediction and offline-ready ranger navigation system for the **Satpura / Pachmarhi Biosphere Reserve (Madhya Pradesh)**, combining **Disaster Management (Domain 03)** and **Satcom / Navigation (Domain 04)**.

## ISRO Data & Telemetry Backbone
- **Bhoonidhi (STAC API):** Live `ResourceSat-2A_LISS3_BOA` optical satellite scene ingestion over Satpura (`bbox: [77.90, 22.30, 78.60, 22.70]`).
- **VEDAS / Bhuvan Schema:** Vegetation fuel dryness (NDVI) and thermal ignition hotspot anchoring.
- **MOSDAC-Compatible Weather Telemetry:** Live wind vector, temperature, and humidity driving downwind fire corridor projections, with built-in offline cache fallback.

## 5-Module Architecture
1. `modules/m1_satellite_ingest.py` — Authenticates with ISRO Bhoonidhi STAC API and caches `ResourceSat-2A` footprints (`data/bhoonidhi_scenes.json`).
2. `modules/m2_fuel_weather.py` — Fetches live surface weather telemetry and pairs it with sector fuel dryness & thermal hotspots (`data/weather_fuel.json`).
3. `modules/m3_corridor_engine.py` — Computes weighted wildfire risk scores and projects directional downwind spread polygons (`data/corridors.geojson`).
4. `modules/m4_nav_alerts.py` — Evaluates threatened forest nodes via ray-casting, calculates flank-safe evacuation routes, and generates `<140-byte` Satcom alert payloads (`data/alerts_routes.json`).
5. `modules/m5_dashboard.py` — Interactive Streamlit + Folium command centre with live wind-shift simulation and toggleable satellite/corridor layers.

## How to Run Locally
```bash
git clone [https://github.com/](https://github.com/)<your-username>/ASTRA.git
cd ASTRA
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
streamlit run modules/m5_dashboard.py