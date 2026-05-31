from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
SAMPLE_DIR = DATA_DIR / "sample"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_PLANNING_DIR = RAW_DIR / "planning"
RAW_UPLOADS_DIR = RAW_DIR / "uploads"
PROCESSED_UPLOADS_DIR = PROCESSED_DIR / "uploads"
DOSSIERS_DIR = PROCESSED_DIR / "dossiers"


def ensure_runtime_dirs() -> None:
    for path in [
        RAW_PLANNING_DIR,
        RAW_UPLOADS_DIR,
        PROCESSED_DIR,
        PROCESSED_UPLOADS_DIR,
        DOSSIERS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)

