import hashlib
import json

from app.core.paths import DOSSIERS_DIR
from app.models.schemas import Dossier


DOSSIER_CACHE_INDEX_PATH = DOSSIERS_DIR / "cache_index.json"


class DossierNotFoundError(ValueError):
    pass


def save_dossier(dossier: Dossier) -> None:
    DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
    (DOSSIERS_DIR / f"{dossier.dossier_id}.json").write_text(
        dossier.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_dossier(dossier_id: str) -> Dossier:
    path = DOSSIERS_DIR / f"{dossier_id}.json"
    if not path.exists():
        raise DossierNotFoundError(f"Unknown dossier: {dossier_id}")
    return Dossier.model_validate_json(path.read_text(encoding="utf-8"))


def cache_key_for_signature(signature: dict) -> str:
    encoded = json.dumps(signature, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_cached_dossier(cache_key: str) -> Dossier | None:
    index = _read_cache_index()
    dossier_id = index.get(cache_key, {}).get("dossier_id")
    if not dossier_id:
        return None
    try:
        return load_dossier(dossier_id)
    except DossierNotFoundError:
        return None


def save_dossier_cache(cache_key: str, dossier: Dossier, signature: dict) -> None:
    index = _read_cache_index()
    index[cache_key] = {
        "dossier_id": dossier.dossier_id,
        "signature": signature,
    }
    DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
    DOSSIER_CACHE_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_cache_index() -> dict:
    if not DOSSIER_CACHE_INDEX_PATH.exists():
        return {}
    try:
        return json.loads(DOSSIER_CACHE_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
