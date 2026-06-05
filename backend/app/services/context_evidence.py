from typing import Any

from app.models.schemas import EvidenceObject, EvidenceType, SiteContext, SiteGeoJsonResponse


def build_site_profile_evidence(site_context: SiteContext) -> EvidenceObject:
    content = (
        f"Demo site profile for {site_context.address}. Commune: {site_context.commune}. "
        f"Approximate coordinates: {site_context.coordinates.lat:.4f}, {site_context.coordinates.lon:.4f}. "
        f"Building type: {site_context.building_type or 'unknown'}. "
        f"Address precision: {site_context.data_quality.address_precision}; "
        f"coordinate precision: {site_context.data_quality.coordinate_precision}. "
        f"Limitations: {'; '.join(site_context.data_quality.limitations)}"
    )
    return EvidenceObject(
        evidence_id=f"ev_site_profile_{site_context.site_id}",
        evidence_type=EvidenceType.site_profile,
        source_id=f"src_site_profile_{site_context.site_id}",
        source_type="site_profile",
        source_subtype="demo_site_profile",
        modality="structured_profile",
        authority_level="demo_data",
        evidence_role="site_identity",
        source_name="Demo site profile",
        content=content,
        supports=["site_identity_location"],
        parser="json",
        metadata={
            "site_id": site_context.site_id,
            "commune": site_context.commune,
            "data_quality": site_context.data_quality.model_dump(mode="json"),
        },
        confidence="medium",
    )


def build_geospatial_evidence(site_context: SiteContext, site_geojson: SiteGeoJsonResponse | None) -> EvidenceObject:
    features = _geojson_context_features(site_geojson)
    feature_summary = ", ".join(
        f"{feature.get('name', 'GeoJSON feature')} ({round(float(feature.get('distance_m', 0)))} m)"
        for feature in features[:5]
    )
    if not feature_summary:
        feature_summary = "No nearby GeoJSON context features were available within the configured radius."
    content = (
        f"Lightweight geospatial context for {site_context.address}. "
        f"The demo coordinate is approximate and is not a cadastral boundary or verified building footprint. "
        f"Nearby context features: {feature_summary}"
    )
    return EvidenceObject(
        evidence_id=f"ev_geo_context_{site_context.site_id}",
        evidence_type=EvidenceType.geospatial,
        source_id="src_demo_geospatial_geojson",
        source_type="geojson",
        source_subtype="demo_coordinate_context",
        modality="geojson",
        authority_level="open_geospatial",
        evidence_role="geospatial_context",
        source_name="Demo site coordinate GeoJSON",
        content=content,
        supports=["site_identity_location"],
        parser="geojson",
        metadata={
            "site_id": site_context.site_id,
            "radius_m": site_geojson.radius_m if site_geojson else None,
            "feature_count": len(features),
            "features": features[:5],
            "limitations": [
                "Coordinates are approximate for MVP context.",
                "GeoJSON context must not be treated as a cadastral or engineering fact.",
            ],
        },
        confidence="low",
    )


def build_context_evidence(site_context: SiteContext, site_geojson: SiteGeoJsonResponse | None) -> list[EvidenceObject]:
    return [
        build_site_profile_evidence(site_context),
        build_geospatial_evidence(site_context, site_geojson),
    ]


def _geojson_context_features(site_geojson: SiteGeoJsonResponse | None) -> list[dict[str, Any]]:
    if site_geojson is None:
        return []
    features = []
    for feature in site_geojson.geojson.get("features", []):
        properties = dict(feature.get("properties") or {})
        if properties.get("feature_type") == "demo_site":
            continue
        features.append(
            {
                "feature_id": properties.get("feature_id"),
                "name": properties.get("name"),
                "feature_type": properties.get("feature_type"),
                "distance_m": properties.get("distance_m"),
                "source_id": properties.get("source_id"),
            }
        )
    return features
