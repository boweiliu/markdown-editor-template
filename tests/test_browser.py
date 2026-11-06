"""The page in a real browser: Suggest mode, comments, accept, outside changes, Read mode.

Runs the server on a spare port against a throwaway folder. Skipped when no Chromium build is available (set
MARKDOWN_EDITOR_CHROMIUM to one; a Studio workspace has /opt/fortress/tilion-fortress/tilion).
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

CHROMIUM = os.environ.get("MARKDOWN_EDITOR_CHROMIUM", "/opt/fortress/tilion-fortress/tilion")
playwright_api = pytest.importorskip("playwright.sync_api")
pytestmark = [
    pytest.mark.skipif(not Path(CHROMIUM).exists(), reason="no Chromium build to drive"),
]

PLAN = """# Plan

The agent wrote this paragraph and wrapped it
at a fixed width, like agents do.

An agent wrote {++this added clause, ++}and {--this removed clause --}and a {~~typo~>fix~~}.

- [ ] a task item
"""


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def server(tmp_path: Path):
    home = tmp_path / "home"
    workspace = home / "workspace"
    workspace.mkdir(parents=True)
    port = free_port()
    env = {
        **os.environ,
        "MARKDOWN_EDITOR_PORT": str(port),
        "MARKDOWN_EDITOR_ROOT": str(home),
        "MARKDOWN_EDITOR_SEARCH_ROOT": str(workspace),
        "MARKDOWN_EDITOR_DATA_DIR": str(tmp_path / "data"),
    }
    process = subprocess.Popen([sys.executable, "-m", "markdown_editor.runner"], env=env)
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    yield url, workspace
    process.terminate()
    process.wait(timeout=10)


def wait_for(condition, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


def test_review_a_plan(server) -> None:
    url, workspace = server
    plan = workspace / "plan.md"
    plan.write_text(PLAN)
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{url}/?path={plan}")
        page.wait_for_selector(".tiptap h1")

        # Opening changes nothing, and Suggest is the default.
        assert "selected" in (page.get_attribute("#mode-suggest", "class") or "")
        assert page.inner_text("#review-counts") == "3 suggestions"
        time.sleep(1.5)
        assert plan.read_text() == PLAN

        # Typing at the end of a wrapped paragraph is saved as an insertion of just the new words.
        page.locator(".tiptap > p").first.click()
        page.evaluate(
            "() => { const p = document.querySelector('.tiptap > p'); const r = document.createRange();"
            " r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }"
        )
        page.keyboard.type(" Sam agrees.")
        assert wait_for(lambda: "like agents do.{++ Sam agrees.++}" in plan.read_text())
        assert "{--The agent" not in plan.read_text()

        # A comment on a selected word, signed.
        page.locator(".tiptap h1").dblclick(position={"x": 20, "y": 20})
        page.keyboard.press("Control+Alt+KeyM")
        page.fill("#popover-field", "Rename this")
        page.fill("#popover-signature", "Sam")
        page.click("#popover-save")
        assert wait_for(lambda: "# {==Plan==}{>>Sam: Rename this<<}" in plan.read_text()), plan.read_text()

        # Accept every suggestion.
        page.click("#accept-all")
        assert wait_for(lambda: "{++" not in plan.read_text() and "{~~" not in plan.read_text())
        text = plan.read_text()
        assert "An agent wrote this added clause, and and a fix." in text
        assert "Sam agrees." in text

        # An agent rewrites the file while the page has nothing unsaved: the page shows the new version.
        plan.write_text(plan.read_text().replace("a task item", "a task the agent renamed"))
        assert wait_for(lambda: "a task the agent renamed" in page.inner_text(".tiptap"), timeout=10)

        # Read mode cannot change the file.
        page.click("#mode-read")
        assert page.get_attribute(".tiptap", "contenteditable") == "false"
        assert errors == []
        browser.close()


def test_toolbar_stays_attached_in_a_narrow_window(server) -> None:
    # In a narrow window the toolbar wraps onto two rows; it must stay directly under the top bar while scrolling.
    url, workspace = server
    plan = workspace / "long.md"
    plan.write_text("# Long\n\n" + "\n\n".join(f"Paragraph {number} " + "words " * 40 for number in range(40)) + "\n")
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": 640, "height": 500})
        page.goto(f"{url}/?path={plan}")
        page.wait_for_selector(".tiptap h1")
        page.mouse.wheel(0, 3000)
        time.sleep(0.5)
        top_bar = page.locator("#topbar").bounding_box()
        toolbar = page.locator("#toolbar").bounding_box()
        assert top_bar is not None and toolbar is not None
        assert abs(top_bar["y"]) < 1
        assert abs(toolbar["y"] - (top_bar["y"] + top_bar["height"])) < 1
        assert toolbar["height"] > 40  # it really did wrap onto two rows
        browser.close()
