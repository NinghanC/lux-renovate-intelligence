from app.core.paths import SAMPLE_DIR
from app.models.schemas import DataQuality, DemoSite, SiteContext
from app.services.json_store import read_json


DEMO_SITES_PATH = SAMPLE_DIR / "demo_sites.json"
GEOSPATIAL_CONTEXT_PATH = SAMPLE_DIR / "geospatial_context.json"


class SiteNotFoundError(ValueError):
    pass


class SiteResolver:
    def __init__(self, path=DEMO_SITES_PATH, geospatial_path=GEOSPATIAL_CONTEXT_PATH):
        self.path = path
        self.geospatial_path = geospatial_path

    def list_sites(self) -> list[DemoSite]:
        if not self.path.exists():
            return []
        data = read_json(self.path)
        return [DemoSite.model_validate(item) for item in data]

    def get_site(self, site_id: str) -> DemoSite:
        for site in self.list_sites():
            if site.site_id == site_id:
                return site
        raise SiteNotFoundError(f"Unknown demo site: {site_id}")

    def build_context(self, site_id: str) -> SiteContext:
        site = self.get_site(site_id)
        geospatial = self._get_geospatial_context(site_id)
        limitations = [
            "Demo coordinates are used for context only and are not a verified cadastral survey.",
            "Building footprint enrichment is reserved for a production data pipeline.",
        ]
        limitations.extend(geospatial.get("limitations", []))
        nearby_features = geospatial.get("nearby_features") or site.available_public_sources
        return SiteContext(
            site_id=site.site_id,
            address=site.input_address or "unknown",
            commune=site.commune,
            coordinates=site.coordinates,
            building_type=site.building_type or "unknown",
            approx_year_built=site.approx_year_built,
            nearby_features=nearby_features,
            geospatial_context=geospatial,
            data_quality=DataQuality(
                address_precision="demo-area" if "area" in site.input_address.lower() else "address-or-site-name",
                coordinate_precision="approximate",
                footprint_available=None if geospatial.get("footprint") is None else True,
                limitations=list(dict.fromkeys(limitations)),
            ),
        )

    def _get_geospatial_context(self, site_id: str) -> dict:
        if not self.geospatial_path.exists():
            return {}
        data = read_json(self.geospatial_path)
        return data.get(site_id, {})
