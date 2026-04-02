import sys
from pathlib import Path

import pytest

from apple_agent_mcp import bootstrap


def test_ensure_domain_paths_uses_installed_packages(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_repo_dir", lambda: Path("/tmp/not-used"))
    monkeypatch.setattr(bootstrap, "_missing_packages", lambda: [])

    before = list(sys.path)

    repo_dir = bootstrap.ensure_domain_paths()

    assert repo_dir == Path("/tmp/not-used")
    assert sys.path == before


def test_ensure_domain_paths_falls_back_to_repo_src(monkeypatch, tmp_path) -> None:
    repo_dir = tmp_path / "repo"
    package = bootstrap.DomainPackage("AppleMail-MCP", "apple_mail_mcp", "apple-mail-mcp")
    src_dir = repo_dir / package.folder / "src"
    src_dir.mkdir(parents=True)

    calls = {"count": 0}

    def fake_missing() -> list[bootstrap.DomainPackage]:
        calls["count"] += 1
        return [package] if calls["count"] == 1 else []

    monkeypatch.setattr(bootstrap, "_repo_dir", lambda: repo_dir)
    monkeypatch.setattr(bootstrap, "_missing_packages", fake_missing)

    before = list(sys.path)
    try:
        resolved = bootstrap.ensure_domain_paths()
        assert resolved == repo_dir
        assert str(src_dir) in sys.path
    finally:
        sys.path[:] = before


def test_ensure_domain_paths_raises_clear_error_when_missing(monkeypatch, tmp_path) -> None:
    repo_dir = tmp_path / "isolated"
    monkeypatch.setattr(bootstrap, "_repo_dir", lambda: repo_dir)
    monkeypatch.setattr(
        bootstrap,
        "_missing_packages",
        lambda: [bootstrap.DomainPackage("AppleMail-MCP", "apple_mail_mcp", "apple-mail-mcp")],
    )

    with pytest.raises(ImportError, match="apple-mail-mcp"):
        bootstrap.ensure_domain_paths()
