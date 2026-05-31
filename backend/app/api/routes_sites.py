from fastapi import APIRouter, HTTPException

from app.models.schemas import DemoSite, SiteContext
from app.services.site_resolver import SiteNotFoundError, SiteResolver


router = APIRouter(prefix="/api/sites", tags=["sites"])
resolver = SiteResolver()


@router.get("", response_model=list[DemoSite])
def list_sites() -> list[DemoSite]:
    return resolver.list_sites()


@router.get("/{site_id}/context", response_model=SiteContext)
def get_site_context(site_id: str) -> SiteContext:
    try:
        return resolver.build_context(site_id)
    except SiteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

