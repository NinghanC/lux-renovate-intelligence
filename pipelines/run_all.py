import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "pipelines" / script)], check=True, cwd=ROOT)


def main() -> None:
    run("download_planning_documents.py")
    run("ingest_planning_documents.py")
    run("build_document_index.py")


if __name__ == "__main__":
    main()

