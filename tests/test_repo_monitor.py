from pathlib import Path

from app.repo_monitor.scanner import compare_manifests, scan_repository


def test_scan_finds_security_and_quality_issues(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "TOKEN = 'demo-secret-value-123456'\n\nprint('debug')\nvalue = eval('1 + 1')\n",
        encoding="utf-8",
    )
    first = scan_repository(tmp_path)
    titles = {f["title"] for f in first["findings"]}
    assert "eval usage" in titles
    assert "debug print" in titles
    assert first["fingerprint"]


def test_manifest_marks_modified_repository_as_changed(tmp_path: Path):
    file = tmp_path / "app.py"
    file.write_text("print('v1')\n", encoding="utf-8")
    first = scan_repository(tmp_path)
    accepted = dict(first)
    file.write_text("print('v2')\n", encoding="utf-8")
    second = scan_repository(tmp_path)
    delta = compare_manifests(accepted, second)
    assert delta["changed"] is True
    assert "app.py" in delta["modified"]
