import hashlib
import os
import time
from pathlib import Path

import pytest

from markdown_editor import files


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_reads_a_markdown_file(root: Path) -> None:
    plan = root / "plan.md"
    plan.write_text("# Plan\n\nSteps.\n")
    record = files.read(str(plan))
    assert record.text == "# Plan\n\nSteps.\n"
    assert record.sha256 == sha(record.text)
    assert record.writable is True
    assert record.name == "plan.md"


def test_relative_paths_are_under_the_workspace(root: Path) -> None:
    (root / "notes").mkdir()
    (root / "notes" / "a.md").write_text("a\n")
    assert files.read("notes/a.md").path == str((root / "notes" / "a.md").resolve())


def test_refuses_paths_outside_the_root(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n")
    with pytest.raises(files.FileProblem) as problem:
        files.read(str(outside))
    assert problem.value.status == 403
    with pytest.raises(files.FileProblem):
        files.read(str(root / ".." / ".." / "outside.md"))


def test_refuses_a_symlink_that_leaves_the_root(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n")
    (root / "link.md").symlink_to(outside)
    with pytest.raises(files.FileProblem) as problem:
        files.read(str(root / "link.md"))
    assert problem.value.status == 403


def test_refuses_credentials_folders(root: Path) -> None:
    secrets = root / "data" / ".secrets"
    secrets.mkdir(parents=True)
    (secrets / "notes.md").write_text("x\n")
    with pytest.raises(files.FileProblem) as problem:
        files.read(str(secrets / "notes.md"))
    assert problem.value.status == 403


def test_other_files_open_read_only(root: Path) -> None:
    script = root / "run.py"
    script.write_text("print(1)\n")
    assert files.read(str(script)).writable is False
    with pytest.raises(files.FileProblem) as problem:
        files.write(str(script), "print(2)\n", None, root / "history")
    assert problem.value.status == 403
    assert script.read_text() == "print(1)\n"


def test_binary_files_are_refused(root: Path) -> None:
    blob = root / "image.md"
    blob.write_bytes(b"\xff\xfe\x00binary")
    with pytest.raises(files.FileProblem) as problem:
        files.read(str(blob))
    assert problem.value.status == 415


def test_write_checks_the_base_version_and_keeps_history(root: Path, tmp_path: Path) -> None:
    plan = root / "plan.md"
    plan.write_text("one\n")
    os.chmod(plan, 0o640)
    history = tmp_path / "history"
    new_sha, _ = files.write(str(plan), "two\n", sha("one\n"), history)
    assert plan.read_text() == "two\n"
    assert new_sha == sha("two\n")
    assert plan.stat().st_mode & 0o777 == 0o640
    kept = [item for item in next(history.iterdir()).iterdir() if item.name != "source.txt"]
    assert [item.read_text() for item in kept] == ["one\n"]

    with pytest.raises(files.FileProblem) as problem:
        files.write(str(plan), "three\n", sha("one\n"), history)
    assert problem.value.status == 409
    assert plan.read_text() == "two\n"

    files.write(str(plan), "three\n", None, history)
    assert plan.read_text() == "three\n"


def test_writing_the_same_text_changes_nothing(root: Path, tmp_path: Path) -> None:
    plan = root / "plan.md"
    plan.write_text("same\n")
    files.write(str(plan), "same\n", sha("same\n"), tmp_path / "history")
    assert not (tmp_path / "history").exists()


def test_history_keeps_only_the_newest_versions(root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(files, "HISTORY_KEEP", 3)
    plan = root / "plan.md"
    plan.write_text("v0\n")
    for number in range(1, 6):
        files.write(str(plan), f"v{number}\n", None, tmp_path / "history")
    folder = next((tmp_path / "history").iterdir())
    kept = sorted(item.read_text() for item in folder.iterdir() if item.name != "source.txt")
    assert kept == ["v2\n", "v3\n", "v4\n"]


def test_finds_markdown_newest_first_and_skips_machine_folders(root: Path) -> None:
    (root / "old.md").write_text("old\n")
    os.utime(root / "old.md", (1_000_000, 1_000_000))
    (root / "docs").mkdir()
    (root / "docs" / "new.md").write_text("new\n")
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "node_modules" / "pkg" / "README.md").write_text("skip\n")
    (root / "notes.txt").write_text("not markdown\n")
    found = files.find_markdown(root)
    assert [item.name for item in found] == ["new.md", "old.md"]


def test_paths_are_shown_under_the_root_name(root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # On Studio /home/user is a link to the volume; files are shown under /home/user, not the volume's path.
    real_home = root.parent
    named_home = tmp_path / "named-home"
    named_home.symlink_to(real_home)
    monkeypatch.setattr(files, "ROOT_NAME", named_home)
    (root / "plan.md").write_text("x\n")
    record = files.read(str(named_home / "workspace" / "plan.md"))
    assert record.path == str(named_home / "workspace" / "plan.md")
    assert [item.path for item in files.find_markdown(root)] == [str(named_home / "workspace" / "plan.md")]


def test_hidden_folders_are_not_listed(root: Path) -> None:
    (root / ".tickets").mkdir()
    (root / ".tickets" / "t-1.md").write_text("ticket\n")
    (root / "notes").mkdir()
    (root / "notes" / "mine.md").write_text("mine\n")
    assert [item.name for item in files.find_markdown(root)] == ["mine.md"]


def test_a_stale_list_is_answered_at_once_and_refreshed(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (root / "first.md").write_text("1\n")
    assert [item.name for item in files.find_markdown()] == ["first.md"]
    (root / "second.md").write_text("2\n")
    assert [item.name for item in files.find_markdown()] == ["first.md"]  # fresh cache
    stamp, found = files._found_cache
    monkeypatch.setattr(files, "_found_cache", (stamp - files.SEARCH_CACHE_SECONDS - 1, found))
    assert [item.name for item in files.find_markdown()] == ["first.md"]  # stale, answered at once
    deadline = time.time() + 5
    while files._refreshing.is_set() and time.time() < deadline:
        time.sleep(0.05)
    assert sorted(item.name for item in files.find_markdown()) == ["first.md", "second.md"]
