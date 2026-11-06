from pathlib import Path

import pytest

from markdown_editor import files, runner


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway home folder the app may open files in; nothing outside it is reachable."""
    home = tmp_path / "home"
    workspace = home / "workspace"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(files, "ROOT", home.resolve())
    monkeypatch.setattr(files, "ROOT_NAME", home.resolve())
    monkeypatch.setattr(files, "SEARCH_ROOT", workspace.resolve())
    monkeypatch.setattr(files, "_found_cache", None)
    monkeypatch.setattr(runner, "HISTORY_DIR", tmp_path / "data" / "history")
    return workspace


@pytest.fixture
def client(root: Path):
    runner.app.config["TESTING"] = True
    with runner.app.test_client() as test_client:
        yield test_client
