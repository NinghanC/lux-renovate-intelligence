from app.core.paths import DOSSIERS_DIR
from app.models.schemas import Dossier


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

