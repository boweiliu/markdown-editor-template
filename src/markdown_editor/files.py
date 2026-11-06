"""Reading and writing the files the editor opens, and finding markdown files to offer."""

import hashlib
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# The editor opens files under this folder (the workspace user's home), like the Files app does. Paths are shown
# and answered under this name even when it is a link to somewhere else (on Studio /home/user is a link).
ROOT_NAME = Path(os.environ.get("MARKDOWN_EDITOR_ROOT", "/home/user")).absolute()
ROOT = ROOT_NAME.resolve()
# Where the picker looks for markdown files.
SEARCH_ROOT = Path(os.environ.get("MARKDOWN_EDITOR_SEARCH_ROOT", "/home/user/workspace")).resolve()
WRITABLE_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".txt"}
READABLE_LIMIT_BYTES = 5 * 1024 * 1024
# Folders that hold credentials or are too large and machine-made to be worth listing.
REFUSED_PARTS = {".secrets"}
SKIPPED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".state",
    ".tasks",
    ".secrets",
    "dist",
    "build",
    "vendor",
    ".cache",
}
# Hidden folders hold machine state, tickets, other repos and app data; people's own files are in visible folders.
SKIP_HIDDEN_DIRS = True
FOUND_LIMIT = 200
SEARCH_DEPTH = 7
SEARCH_CACHE_SECONDS = 30.0
HISTORY_KEEP = 30


class FileProblem(Exception):
    """A request for a file that cannot be honoured; `status` is the HTTP status to answer with."""

    def __init__(self, detail: str, status: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


def resolve(path_text: str) -> Path:
    """The absolute file a request names, refused when it is outside ROOT or under a credentials folder."""
    if not path_text or "\x00" in path_text:
        raise FileProblem("No file named.", 400)
    raw = Path(path_text).expanduser()
    if not raw.is_absolute():
        raw = SEARCH_ROOT / raw
    path = raw.resolve()
    if path != ROOT and ROOT not in path.parents:
        raise FileProblem(f"Only files under {ROOT} can be opened.", 403)
    if any(part in REFUSED_PARTS for part in path.parts):
        raise FileProblem("Files in a credentials folder are not opened here.", 403)
    return path


def shown(path: Path) -> str:
    """`path` (resolved) as people know it: under ROOT_NAME rather than wherever that link points."""
    if path == ROOT:
        return str(ROOT_NAME)
    if ROOT in path.parents:
        return str(ROOT_NAME / path.relative_to(ROOT))
    return str(path)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    text: str
    sha256: str
    size: int
    mtime: float
    writable: bool


def read(path_text: str) -> FileRecord:
    path = resolve(path_text)
    if not path.is_file():
        raise FileProblem(f"There is no file at {path}.", 404)
    size = path.stat().st_size
    if size > READABLE_LIMIT_BYTES:
        raise FileProblem(f"{path.name} is {size // 1024 // 1024} MB; the editor opens files up to 5 MB.", 413)
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FileProblem(f"{path.name} is not a text file.", 415) from error
    return FileRecord(
        path=shown(path),
        name=path.name,
        text=text,
        sha256=sha256_of(data),
        size=size,
        mtime=path.stat().st_mtime,
        writable=path.suffix.lower() in WRITABLE_SUFFIXES and os.access(path, os.W_OK),
    )


def version(path_text: str) -> tuple[str, float]:
    path = resolve(path_text)
    if not path.is_file():
        raise FileProblem(f"There is no file at {path}.", 404)
    return sha256_of(path.read_bytes()), path.stat().st_mtime


_write_lock = threading.Lock()


def write(path_text: str, text: str, base_sha256: str | None, history_dir: Path) -> tuple[str, float]:
    """Write `text` to the file, refusing (409) when it changed since `base_sha256`; None writes regardless.

    The version being replaced is kept under `history_dir` first, so an editor mistake can always be undone.
    """
    path = resolve(path_text)
    if path.suffix.lower() not in WRITABLE_SUFFIXES:
        raise FileProblem(f"Only markdown and text files are saved here, not {path.suffix or 'this kind of file'}.", 403)
    if not path.is_file():
        raise FileProblem(f"There is no file at {path}.", 404)
    data = text.encode("utf-8")
    with _write_lock:
        current = path.read_bytes()
        current_sha = sha256_of(current)
        if base_sha256 is not None and base_sha256 != current_sha:
            raise FileProblem("The file was changed outside the editor.", 409)
        if current == data:
            return current_sha, path.stat().st_mtime
        keep_history(path, current, history_dir)
        mode = path.stat().st_mode & 0o7777
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".saving", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    return sha256_of(data), path.stat().st_mtime


def history_folder(path: Path, history_dir: Path) -> Path:
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    return history_dir / f"{path.name}-{digest}"


def keep_history(path: Path, data: bytes, history_dir: Path) -> None:
    folder = history_folder(path, history_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source.txt").write_text(str(path) + "\n")
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + f"-{time.time_ns() % 1_000_000_000:09d}"
    (folder / f"{stamp}{path.suffix}").write_bytes(data)
    versions = sorted(item for item in folder.iterdir() if item.name != "source.txt")
    for old in versions[:-HISTORY_KEEP]:
        old.unlink(missing_ok=True)


@dataclass(frozen=True)
class FoundFile:
    path: str
    name: str
    size: int
    mtime: float


_found_cache: tuple[float, list[FoundFile]] | None = None
_found_lock = threading.Lock()
_refreshing = threading.Event()
SEARCH_BUDGET_SECONDS = 3.0


def scan_markdown(root: Path, budget_seconds: float = SEARCH_BUDGET_SECONDS) -> list[FoundFile]:
    """Markdown files under `root`, most recently changed first; the walk stops after `budget_seconds`."""
    found: list[FoundFile] = []
    base_depth = len(root.parts)
    deadline = time.monotonic() + budget_seconds
    for folder, dirs, names in os.walk(root):
        if time.monotonic() > deadline:
            break
        depth = len(Path(folder).parts) - base_depth
        dirs[:] = sorted(name for name in dirs if name not in SKIPPED_DIRS and not (SKIP_HIDDEN_DIRS and name.startswith(".")))
        if depth >= SEARCH_DEPTH:
            dirs[:] = []
        for name in names:
            if Path(name).suffix.lower() not in {".md", ".markdown"}:
                continue
            full = Path(folder) / name
            try:
                stat = full.stat()
            except OSError:
                continue
            found.append(FoundFile(path=shown(full.resolve()), name=name, size=stat.st_size, mtime=stat.st_mtime))
    found.sort(key=lambda item: item.mtime, reverse=True)
    return found[:FOUND_LIMIT]


def _refresh_in_background() -> None:
    global _found_cache
    try:
        found = scan_markdown(SEARCH_ROOT)
        with _found_lock:
            _found_cache = (time.time(), found)
    finally:
        _refreshing.clear()


def find_markdown(root: Path | None = None) -> list[FoundFile]:
    """Markdown files to offer on the start page.

    For the search root the answer is cached: a fresh list is returned as is, a stale one is returned at once while
    a new scan runs in the background (a cold scan of a big workspace takes seconds on Studio's sandboxed disk).
    """
    global _found_cache
    if root is not None and root != SEARCH_ROOT:
        return scan_markdown(root)
    with _found_lock:
        cached = _found_cache
    if cached is None:
        found = scan_markdown(SEARCH_ROOT)
        with _found_lock:
            _found_cache = (time.time(), found)
        return found
    if time.time() - cached[0] >= SEARCH_CACHE_SECONDS and not _refreshing.is_set():
        _refreshing.set()
        threading.Thread(target=_refresh_in_background, daemon=True).start()
    return cached[1]
