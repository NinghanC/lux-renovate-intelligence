from datetime import datetime, timezone
from pathlib import Path

from app.core.paths import DATA_DIR
from app.models.evaluation import EvaluationRunReport


EVALUATION_RUNS_DIR = DATA_DIR / "evaluation" / "runs"


def write_report(report: EvaluationRunReport, output_dir: Path = EVALUATION_RUNS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{timestamp}_{report.mode}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path
