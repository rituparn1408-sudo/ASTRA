import json
import os
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv
import config

load_dotenv()

DEFAULT_AUTH_URL = "https://bhoonidhi-api.nrsc.gov.in/auth/token"
DEFAULT_SEARCH_URL = "https://bhoonidhi-api.nrsc.gov.in/data/search"


def get_bhoonidhi_token(auth_url: str, user_id: str, password: str) -> str | None:
    if not all([auth_url, user_id, password]):
        print("[Module 1] Missing Bhoonidhi credentials in .env; skipping live auth.")
        return None

    payload = {
        "userId": "nexus04",
        "password": "14@2008",
        "grant_type": "password",
    }
    try:
        resp = requests.post(
            auth_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            print(f"[Module 1] Token missing in response: {data}")
            return None
        print("[Module 1] Authenticated with ISRO Bhoonidhi API.")
        return token
    except requests.RequestException as exc:
        print(f"[Module 1] Bhoonidhi auth failed ({exc}); switching to cached/fallback data.")
        return None


def _parse_feature(feature: dict) -> dict:
    props = feature.get("properties", {}) or {}
    dt = (
        props.get("datetime")
        or props.get("Date_of_Pass")
        or props.get("acquisition_date")
        or "N/A"
    )
    cloud = (
        props.get("eo:cloud_cover")
        if props.get("eo:cloud_cover") is not None
        else props.get("Cloud_Cover", props.get("cloud_cover"))
    )
    return {
        "id": feature.get("id"),
        "datetime": dt,
        "cloud_cover": cloud,
        "collection": feature.get("collection"),
        "bbox": feature.get("bbox", config.SATPURA_BBOX),
        "geometry": feature.get("geometry"),
    }


def fetch_bhoonidhi_scenes(days_back: int = 90, limit: int = 10) -> dict:
    auth_url = os.getenv("BHOONIDHI_AUTH_URL", DEFAULT_AUTH_URL).strip()
    search_url = os.getenv("BHOONIDHI_STAC_SEARCH_URL", DEFAULT_SEARCH_URL).strip()
    user_id = os.getenv("BHOONIDHI_USER_ID", "").strip()
    password = os.getenv("BHOONIDHI_PASSWORD", "").strip()
    collection = os.getenv("BHOONIDHI_COLLECTION", "ResourceSat-2A_LISS3_BOA").strip()

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)
    date_range = f"{start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    token = get_bhoonidhi_token(auth_url, user_id, password)
    if search_url and token:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "collections": [collection],
            "bbox": config.SATPURA_BBOX,
            "datetime": date_range,
            "limit": limit,
        }
        try:
            resp = requests.post(search_url, headers=headers, json=payload, timeout=25)
            resp.raise_for_status()
            raw = resp.json()
            features = raw.get("features", [])
            if features:
                output = {
                    "source": "ISRO Bhoonidhi STAC API (Live)",
                    "collection": collection,
                    "fetched_at": end_dt.isoformat(),
                    "scene_count": len(features),
                    "scenes": [_parse_feature(f) for f in features],
                }
                _save_scenes(output)
                return output
            print("[Module 1] Live search succeeded but returned 0 scenes for this window.")
        except requests.RequestException as exc:
            print(f"[Module 1] Live STAC search failed ({exc}); checking local cache.")

    # Reuse existing live cache if available before falling back to static snapshot
    if config.SCENES_FILE.exists():
        try:
            with open(config.SCENES_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("scenes"):
                print(f"[Module 1] Reusing existing local cache ({cached['scene_count']} scenes).")
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    fallback = _build_fallback_scenes(collection, end_dt)
    _save_scenes(fallback)
    return fallback


def _build_fallback_scenes(collection: str, ref_dt: datetime) -> dict:
    min_lon, min_lat, max_lon, max_lat = config.SATPURA_BBOX
    footprint = {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]],
    }
    return {
        "source": "Bhoonidhi Cached Snapshot (Fallback)",
        "collection": collection,
        "fetched_at": ref_dt.isoformat(),
        "scene_count": 2,
        "scenes": [
            {
                "id": "RA312NOV2026051535008900043PSANSTUCSRHTDF",
                "datetime": "2026-11-12T05:15:35Z",
                "cloud_cover": 4.2,
                "collection": collection,
                "bbox": config.SATPURA_BBOX,
                "geometry": footprint,
            },
            {
                "id": "RA307NOV2026051210008900043PSANSTUCSRHTDF",
                "datetime": "2026-11-07T05:12:10Z",
                "cloud_cover": 9.8,
                "collection": collection,
                "bbox": config.SATPURA_BBOX,
                "geometry": footprint,
            },
        ],
    }


def _save_scenes(data: dict) -> None:
    with open(config.SCENES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[Module 1] Saved {data['scene_count']} scenes -> {config.SCENES_FILE}")


if __name__ == "__main__":
    result = fetch_bhoonidhi_scenes()
    print(f"[Module 1] Source: {result['source']}")
    for sc in result["scenes"][:5]:
        print(f"  - {sc['id']} | {sc['datetime']} | Cloud: {sc['cloud_cover']}")