import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(module: str) -> None:
    subprocess.run([sys.executable, "-m", f"pipelines.{module}"], check=True, cwd=ROOT)


def main() -> None:
    run("download_planning_documents")
    run("ingest_planning_documents")
    run("build_document_index")


if __name__ == "__main__":
    main()

