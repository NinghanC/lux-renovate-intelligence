from pathlib import Path


def test_pipeline_scripts_do_not_mutate_sys_path():
    for path in Path("pipelines").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "sys.path" not in source, f"{path} should rely on package installation, not sys.path mutation."
