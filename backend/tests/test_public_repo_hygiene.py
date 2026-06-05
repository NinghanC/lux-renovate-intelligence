import subprocess
from pathlib import Path


TEXT_FILE_SUFFIXES = {
    "",
    ".css",
    ".env",
    ".example",
    ".html",
    ".json",
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
}


def test_tracked_text_files_do_not_contain_chinese_characters():
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    offenders: list[str] = []
    for raw_path in result.stdout.splitlines():
        path = Path(raw_path)
        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any("\u4e00" <= character <= "\u9fff" for character in content):
            offenders.append(raw_path)

    assert offenders == []
