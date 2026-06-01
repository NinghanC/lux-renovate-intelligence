import math
from copy import deepcopy

from app.core.paths import SAMPLE_DIR
from app.models.schemas import Coordinates, SiteGeoJsonResponse
from app.services.json_store import read_json


GEOJSON_PATH = SAMPLE_DIR / "demo_geospatial.geojson"
EARTH_RADIUS_M = 6371008.8


def haversine_distance_m(left: Coordinates, right: Coordinates) -> float:
    lat1 = math.radians(left.lat)
    lat2 = math.radians(right.lat)
    delta_lat = math.radians(right.lat - left.lat)
    delta_lon = math.radians(right.lon - left.lon)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


class GeoJsonService:
    def __init__(self, path=GEOJSON_PATH):
        self.path = path

    def build_site_geojson(
        self,
        *,
        site_id: str,
        coordinates: Coordinates,
        radius_m: float = 1000,
    ) -> SiteGeoJsonResponse:
        if not self.path.exists():
            return SiteGeoJsonResponse(site_id=site_id, radius_m=radius_m, geojson={"type": "FeatureCollection", "features": []})

        payload = read_json(self.path)
        features = []
        for feature in payload.get("features", []):
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Point":
                continue
            raw_coordinates = geometry.get("coordinates") or []
            if len(raw_coordinates) < 2:
                continue
            feature_coordinates = Coordinates(lat=float(raw_coordinates[1]), lon=float(raw_coordinates[0]))
            distance = haversine_distance_m(coordinates, feature_coordinates)
            properties = feature.get("properties") or {}
            if properties.get("site_id") not in {site_id, None} and distance > radius_m:
                continue
            if distance > radius_m and properties.get("feature_type") != "demo_site":
                continue
            enriched = deepcopy(feature)
            enriched.setdefault("properties", {})
            enriched["properties"]["distance_m"] = round(distance, 1)
            enriched["properties"]["source_id"] = "src_demo_geospatial_geojson"
            features.append(enriched)

        return SiteGeoJsonResponse(
            site_id=site_id,
            radius_m=radius_m,
            geojson={"type": "FeatureCollection", "features": features},
        )
