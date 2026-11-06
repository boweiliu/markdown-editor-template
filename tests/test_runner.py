import hashlib
from pathlib import Path


def test_page_and_health(client) -> None:
    page = client.get("/?path=/x.md")
    assert page.status_code == 200
    assert b'id="editor"' in page.data
    assert "script-src 'self'" in page.headers["Content-Security-Policy"]
    assert client.get("/health").get_json() == {"status": "ok"}


def test_open_save_and_conflict(client, root: Path) -> None:
    plan = root / "plan.md"
    plan.write_text("# Plan\n")
    opened = client.get("/api/file", query_string={"path": str(plan)}).get_json()
    assert opened["text"] == "# Plan\n"
    assert opened["writable"] is True

    saved = client.put("/api/file", json={"path": str(plan), "text": "# Plan{++ v2++}\n", "base_sha256": opened["sha256"]})
    assert saved.status_code == 200
    assert plan.read_text() == "# Plan{++ v2++}\n"
    assert saved.get_json()["sha256"] == hashlib.sha256(plan.read_bytes()).hexdigest()

    version = client.get("/api/file/version", query_string={"path": str(plan)}).get_json()
    assert version["sha256"] == saved.get_json()["sha256"]

    stale = client.put("/api/file", json={"path": str(plan), "text": "lost\n", "base_sha256": opened["sha256"]})
    assert stale.status_code == 409
    assert "changed outside" in stale.get_json()["detail"]
    assert plan.read_text() == "# Plan{++ v2++}\n"


def test_bad_requests_are_explained(client, root: Path) -> None:
    assert client.put("/api/file", json={"path": 3}).status_code == 400
    missing = client.get("/api/file", query_string={"path": str(root / "nope.md")})
    assert missing.status_code == 404
    assert "no file" in missing.get_json()["detail"]
    outside = client.get("/api/file", query_string={"path": "/etc/passwd"})
    assert outside.status_code == 403


def test_raw_download(client, root: Path) -> None:
    plan = root / "plan.md"
    plan.write_text("raw {>>note<<}\n")
    raw = client.get("/api/file/raw", query_string={"path": str(plan), "download": "1"})
    assert raw.data == b"raw {>>note<<}\n"
    assert "attachment" in raw.headers["Content-Disposition"]


def test_lists_files(client, root: Path) -> None:
    (root / "a.md").write_text("a\n")
    listed = client.get("/api/files").get_json()
    assert listed["root"] == str(root.resolve())
    assert [item["name"] for item in listed["files"]] == ["a.md"]
