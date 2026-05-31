from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documents import router as documents_router
from app.api.routes_dossiers import router as dossiers_router
from app.api.routes_health import router as health_router
from app.api.routes_sites import router as sites_router
from app.core.config import settings
from app.core.paths import ensure_runtime_dirs


ensure_runtime_dirs()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Evidence-backed renovation readiness assistant MVP for SECO-style take-home challenge.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sites_router)
app.include_router(documents_router)
app.include_router(dossiers_router)

