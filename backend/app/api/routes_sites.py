from fastapi import APIRouter, HTTPException

from app.models.schemas import DemoSite, SiteContext, SiteGeoJsonResponse
from app.services.geospatial import GeoJsonService
from app.services.site_resolver import SiteNotFoundError, SiteResolver


router = APIRouter(prefix="/api/sites", tags=["sites"])
resolver = SiteResolver()
geojson_service = GeoJsonService()


@router.get("", response_model=list[DemoSite])
def list_sites() -> list[DemoSite]:
    return resolver.list_sites()


@router.get("/{site_id}/context", response_model=SiteContext)
def get_site_context(site_id: str) -> SiteContext:
    try:
        return resolver.build_context(site_id)
    except SiteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{site_id}/geojson", response_model=SiteGeoJsonResponse)
def get_site_geojson(site_id: str, radius_m: float = 1000) -> SiteGeoJsonResponse:
    try:
        site = resolver.get_site(site_id)
        return geojson_service.build_site_geojson(
            site_id=site.site_id,
            coordinates=site.coordinates,
            radius_m=radius_m,
        )
    except SiteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
