import hashlib
import json
import logging
import re
import threading
from pathlib import Path

from app.core.paths import DOSSIERS_DIR
from app.models.schemas import Dossier


DOSSIER_CACHE_INDEX_PATH = DOSSIERS_DIR / "cache_index.json"
DOSSIER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
CACHE_KEY_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_CACHE_INDEX_LOCK = threading.RLock()
logger = logging.getLogger(__name__)


class DossierNotFoundError(ValueError):
    pass


class InvalidDossierIdError(ValueError):
    pass


def save_dossier(dossier: Dossier) -> None:
    DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
    _dossier_path(dossier.dossier_id).write_text(
        dossier.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_dossier(dossier_id: str) -> Dossier:
    try:
        path = _dossier_path(dossier_id)
    except InvalidDossierIdError as exc:
        raise DossierNotFoundError(f"Unknown dossier: {dossier_id}") from exc
    if not path.exists():
        raise DossierNotFoundError(f"Unknown dossier: {dossier_id}")
    return Dossier.model_validate_json(path.read_text(encoding="utf-8"))


def cache_key_for_signature(signature: dict) -> str:
    encoded = json.dumps(signature, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_cached_dossier(cache_key: str) -> Dossier | None:
    if not _valid_cache_key(cache_key):
        return None
    with _CACHE_INDEX_LOCK:
        index = _read_cache_index()
    dossier_id = index.get(cache_key, {}).get("dossier_id")
    if not dossier_id:
        return None
    try:
        return load_dossier(dossier_id)
    except DossierNotFoundError:
        return None


def save_dossier_cache(cache_key: str, dossier: Dossier, signature: dict) -> None:
    if not _valid_cache_key(cache_key):
        raise ValueError("Invalid dossier cache key.")
    with _CACHE_INDEX_LOCK:
        index = _read_cache_index()
        index[cache_key] = {
            "dossier_id": dossier.dossier_id,
            "signature": signature,
        }
        DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
        _write_cache_index(index)


def _read_cache_index() -> dict:
    if not DOSSIER_CACHE_INDEX_PATH.exists():
        return {}
    try:
        return json.loads(DOSSIER_CACHE_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable dossier cache index at %s: %s", DOSSIER_CACHE_INDEX_PATH, exc)
        return {}


def _write_cache_index(index: dict) -> None:
    temporary_path = DOSSIER_CACHE_INDEX_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(DOSSIER_CACHE_INDEX_PATH)


def _dossier_path(dossier_id: str) -> Path:
    if not DOSSIER_ID_PATTERN.fullmatch(dossier_id):
        raise InvalidDossierIdError("Dossier ID contains unsafe characters.")
    base = DOSSIERS_DIR.resolve()
    path = (base / f"{dossier_id}.json").resolve()
    if base != path.parent:
        raise InvalidDossierIdError("Dossier path escapes the dossier directory.")
    return path


def _valid_cache_key(cache_key: str) -> bool:
    return bool(CACHE_KEY_PATTERN.fullmatch(cache_key))
