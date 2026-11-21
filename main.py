from modules.m1_satellite_ingest import fetch_bhoonidhi_scenes
from modules.m2_fuel_weather import build_fuel_and_hotspots
from modules.m3_corridor_engine import generate_corridors
from modules.m4_nav_alerts import generate_nav_and_alerts


def run_pipeline():
    print("=== ASTRA: Satpura Wildfire Corridor Tracker Pipeline ===")
    fetch_bhoonidhi_scenes()
    build_fuel_and_hotspots()
    corridors = generate_corridors(save_output=True)
    generate_nav_and_alerts(corridors_geojson=corridors, save_output=True)
    print("=== Pipeline Complete. Launch dashboard with: streamlit run modules/m5_dashboard.py ===")


if __name__ == "__main__":
    run_pipeline()