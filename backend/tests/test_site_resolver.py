from app.services.site_resolver import SiteResolver


def test_demo_sites_and_context_are_available():
    resolver = SiteResolver()
    sites = resolver.list_sites()

    assert len(sites) >= 3
    context = resolver.build_context(sites[0].site_id)
    assert context.site_id == sites[0].site_id
    assert context.data_quality.footprint_available is None
    assert context.data_quality.limitations
    assert context.geospatial_context
