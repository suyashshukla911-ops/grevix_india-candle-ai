from pathlib import Path

from app.sentinel.scanner import scan
from app.sentinel.service import RepositoryService


def test_scan_detects_eval(tmp_path: Path):
    repo = tmp_path / 'repo'; seed = tmp_path / 'seed'; repo.mkdir(); seed.mkdir()
    (repo / 'src').mkdir(); (repo / 'src' / 'x.py').write_text("value = eval('1')\n", encoding='utf-8')
    result = scan(repo)
    assert any(f.rule == 'dynamic-eval' for f in result.findings)


def test_stale_after_repository_update(tmp_path: Path):
    repo = tmp_path / 'repo'; seed = tmp_path / 'seed'; repo.mkdir(); seed.mkdir()
    (repo / 'requirements.txt').write_text('numpy>=2.2\n', encoding='utf-8')
    (seed / 'requirements.txt').write_text('numpy>=2.2\n', encoding='utf-8')
    service = RepositoryService(repo, tmp_path / 'state.json', seed)
    service.scan()
    assert service.status()['state'] == 'CURRENT'
    (repo / 'requirements.txt').write_text('numpy==2.3.0\n', encoding='utf-8')
    status = service.status()
    assert status['state'] == 'STALE'
    assert status['changes']['dependencies_changed'] is True
