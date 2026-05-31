import json
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def read_jsonl(path: Path, model: type[T]) -> list[T]:
    if not path.exists():
        return []
    rows: list[T] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(model.model_validate_json(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json() + "\n")


def append_jsonl(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json() + "\n")

