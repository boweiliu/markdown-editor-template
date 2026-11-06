"""Serves the Markdown Editor: the page, and reading and writing the markdown files it opens."""

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory
from werkzeug.serving import run_simple

from markdown_editor import files

PORT = int(os.environ.get("MARKDOWN_EDITOR_PORT", "8131"))
HOST = os.environ.get("MARKDOWN_EDITOR_HOST", "127.0.0.1")
DATA_DIR = Path(os.environ.get("MARKDOWN_EDITOR_DATA_DIR", "data/.apps/markdown-editor"))
# Earlier versions of every file the editor saved over, newest kept per file (files.HISTORY_KEEP).
HISTORY_DIR = DATA_DIR / "history"
WEB = Path(__file__).parent / "web"
ICON = next(
    (candidate for candidate in (Path(__file__).parent / "icon.svg", Path(__file__).resolve().parents[2] / "icon.svg") if candidate.is_file()),
    Path(__file__).parent / "icon.svg",
)
# The shell's page modules, served from this origin (a module import is a cookie-less fetch).
SHELL_STATIC_MODULES_DIR = Path("system/apps/system_interface/imbue/system_interface/static/_static")
SHELL_STATIC_MODULE_NAMES = ("app_contract.js", "context_menu.js")

# The page loads only its own files; it is reachable from the internet once the workspace is shared.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'report-sample'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; frame-src 'none'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; report-uri /_csp-report"
)

logger = logging.getLogger("markdown_editor")
app = Flask("markdown_editor", static_folder=None)


def _error(detail: str, status: int) -> tuple[Response, int]:
    return jsonify(detail=detail), status


@app.errorhandler(files.FileProblem)
def file_problem(problem: files.FileProblem) -> tuple[Response, int]:
    return _error(problem.detail, problem.status)


@app.after_request
def security_headers(response: Response) -> Response:
    if response.mimetype == "text/html":
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def index() -> Response:
    """The page; `?path=` names the file to open, `?mode=` (suggest, edit, read) overrides the saved mode."""
    return send_file(WEB / "index.html", max_age=0)


@app.get("/assets/<path:name>")
def assets(name: str) -> Response:
    # Built file names carry a content hash, so they can be cached for good.
    return send_from_directory(WEB / "assets", name, max_age=31536000)


@app.get("/icon.svg")
def icon() -> Response:
    return send_file(ICON, mimetype="image/svg+xml", max_age=0)


@app.get("/health")
def health() -> Response:
    return jsonify(status="ok")


@app.get("/api/file")
def get_file() -> Response:
    """One file's text and version, and whether the editor may save it."""
    record = files.read(request.args.get("path", ""))
    return jsonify(record.__dict__)


@app.get("/api/file/version")
def get_version() -> Response:
    """The file's current version, which the page checks to notice outside changes."""
    sha256, mtime = files.version(request.args.get("path", ""))
    return jsonify(sha256=sha256, mtime=mtime)


@app.get("/api/file/raw")
def get_raw() -> Response:
    """The file exactly as saved; `download=1` saves it under its own name."""
    path = files.resolve(request.args.get("path", ""))
    if not path.is_file():
        abort(404)
    as_download = request.args.get("download") == "1"
    return send_file(path, mimetype="text/plain; charset=utf-8", as_attachment=as_download, download_name=path.name, max_age=0)


@app.put("/api/file")
def put_file() -> tuple[Response, int] | Response:
    """Save the file. `base_sha256` is the version the edit started from; the save is refused (409) if the file
    changed since, unless it is null."""
    body: Any = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("text"), str) or not isinstance(body.get("path"), str):
        return _error("Send JSON with path and text.", 400)
    base = body.get("base_sha256")
    if base is not None and not isinstance(base, str):
        return _error("base_sha256 must be a string or null.", 400)
    sha256, mtime = files.write(body["path"], body["text"], base, HISTORY_DIR)
    return jsonify(sha256=sha256, mtime=mtime)


@app.get("/api/files")
def list_files() -> Response:
    """Markdown files in the workspace, most recently changed first."""
    found = files.find_markdown()
    return jsonify(root=files.shown(files.SEARCH_ROOT), files=[item.__dict__ for item in found])


@app.post("/_csp-report")
def csp_report() -> tuple[str, int]:
    logger.error("Content-Security-Policy blocked: %s", request.get_data(as_text=True)[:2000])
    return "", 204


@app.get("/_static/<basename>")
def shell_module(basename: str) -> Response:
    if basename not in SHELL_STATIC_MODULE_NAMES:
        abort(404)
    module = SHELL_STATIC_MODULES_DIR.resolve() / basename
    if not module.is_file():
        abort(404)
    return send_file(module, mimetype="text/javascript", max_age=0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(message)s")
    # Warm the start page's file list while the first window is still loading.
    threading.Thread(target=files.find_markdown, daemon=True).start()
    run_simple(HOST, PORT, app, threaded=True)


if __name__ == "__main__":
    main()
