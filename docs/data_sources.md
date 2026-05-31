# Data Sources

## Included In The MVP

The MVP uses official public planning documents that are small enough to download and parse locally.

| Commune | Source | Local use |
| --- | --- | --- |
| Luxembourg | Ville de Luxembourg PAP Laangfur | PDF parsing and planning evidence retrieval |
| Luxembourg | Ville de Luxembourg PAG modification 2025-09 | PDF parsing and planning evidence retrieval |
| Diekirch | Commune de Diekirch PAG/PAP PDF | Second commune retrieval sample |
| Mamer | Commune de Mamer Steinchenwies PAG PDF | Third demo commune retrieval sample |

Source URLs are listed in `data/sample/planning_sources.json`.

## Referenced For Production

- data.public.lu PAG datasets: useful for full public planning ingestion, but some ZIP files are too large for the local MVP.
- Geoportail API: useful for production map layers and geospatial enrichment.
- BD-Adresses: useful for address geocoding context; not treated as exact building entry evidence.
- BD-L-BATI3D: useful for building footprints; MVP does not infer engineering facts from it.

## Data Handling Notes

- Public documents are used only as planning evidence.
- Uploaded documents stay on the local machine.
- No SECO internal data or customer confidential data is used.
- Demo coordinates are contextual and not cadastral survey evidence.
- `data/sample/geospatial_context.json` provides lightweight public-data-style site context and explicitly marks footprints as not verified.
