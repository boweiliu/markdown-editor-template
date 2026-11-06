---
name: import-markdown-editor
description: Install the Markdown Editor (review agent-written markdown with suggestions and comments saved as CriticMarkup) on a Studio workspace from its repository, or update an existing install. Use when someone asks for the Markdown Editor, a markdown viewer or redline editor, or gives this repo's URL.
---

# Install or update the Markdown Editor

The app lives in its own repository and runs from a clone at `.external_worktrees/markdown-editor/`. It needs no
account, key or connection. Run everything from the workspace root (`/home/user/workspace`).

1. **Get the code.** New install: `git clone <repo url> .external_worktrees/markdown-editor`. Update:
   `git -C .external_worktrees/markdown-editor pull --ff-only`. A private repo is cloned through the workspace's
   GitHub connection (ask for it through the `connect-external-service` skill first); a public one needs nothing.
2. **Check the port.** The app uses 8131. If `grep -l 8131 system/supervisord.conf.d/*.conf` names another program,
   pick a free port and change it in `deploy/markdown-editor.conf` and `deploy/install.py` (`docs/setup.md` says how).
3. **Install and start:** `python3 .external_worktrees/markdown-editor/deploy/install.py`. It must end with
   `markdown-editor is answering at http://127.0.0.1:8131/health`; if not, read
   `/var/log/supervisor/markdown-editor-stderr.log`.
4. **Show it:** `uv run --no-sync workspace-layout open markdown-editor --beside`, or open a file directly with
   `--path "/?path=/home/user/workspace/<file>.md"`.
5. **Save the wiring:** commit `system/supervisord.conf.d/markdown-editor.conf` in the workspace.

To hand someone a file to review, link `<the app's link from workspace-layout list>/?path=<absolute path>`. Their
suggestions and comments land in the file as CriticMarkup (`{++added++}`, `{--removed--}`, `{~~old~>new~~}`,
`{==text==}{>>comment<<}`); read them there, and accept or reject them by editing the marks out.
