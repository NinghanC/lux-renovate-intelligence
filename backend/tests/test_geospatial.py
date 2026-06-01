from app.models.schemas import Coordinates
from app.services.geospatial import GeoJsonService, haversine_distance_m


def test_haversine_distance_for_same_coordinate_is_zero():
    coordinate = Coordinates(lat=49.5869, lon=6.0887)
    assert haversine_distance_m(coordinate, coordinate) == 0


def test_site_geojson_returns_distance_properties():
    response = GeoJsonService().build_site_geojson(
        site_id="demo_lux_laangfur_001",
        coordinates=Coordinates(lat=49.5869, lon=6.0887),
        radius_m=1000,
    )

    assert response.geojson["features"]
    assert all("distance_m" in feature["properties"] for feature in response.geojson["features"])
