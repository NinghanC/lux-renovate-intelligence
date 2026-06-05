import urllib.request
from pathlib import Path

from app.core.paths import RAW_PLANNING_DIR, SAMPLE_DIR, ensure_runtime_dirs
from app.services.json_store import read_json


SOURCES_PATH = SAMPLE_DIR / "planning_sources.json"


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "LuxRenovate Intelligence local data pipeline"})
    with urllib.request.urlopen(request, timeout=60) as response:
        target.write_bytes(response.read())


def main() -> None:
    ensure_runtime_dirs()
    sources = read_json(SOURCES_PATH)
    for source in sources:
        filename = source["local_filename"]
        target = RAW_PLANNING_DIR / filename
        if target.exists() and target.stat().st_size > 0:
            print(f"SKIP existing {target}")
            continue
        print(f"DOWNLOAD {source['url']} -> {target}")
        try:
            download(source["url"], target)
        except Exception as exc:
            print(f"WARN failed to download {source['document_id']}: {exc}")
    print("Done.")


if __name__ == "__main__":
    main()
