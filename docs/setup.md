# Setup

The app needs no account, key or outside connection. It reads and writes files on the workspace it runs on.

1. Clone the repo into the workspace: `git clone <repo url> .external_worktrees/markdown-editor` from
   `/home/user/workspace`. Check: `ls .external_worktrees/markdown-editor/app.toml`.
2. Install and start: `python3 .external_worktrees/markdown-editor/deploy/install.py`. It installs the clone as a uv
   tool (editable, so a later pull is live after a restart), writes `system/supervisord.conf.d/markdown-editor.conf`,
   has supervisord pick it up, and waits for the app. Check: it prints `markdown-editor is answering at
   http://127.0.0.1:8131/health`, and `supervisorctl status markdown-editor` says RUNNING.
3. Open it: the launcher lists Markdown Editor, or run `uv run --no-sync workspace-layout open markdown-editor`.
   Check: the start page lists the workspace's markdown files.

Port 8131 is the default. If it is taken on a workspace, change it in `deploy/markdown-editor.conf` (the
`--url`, and put `MARKDOWN_EDITOR_PORT=<port>` in front of the start command with `env`) and in `deploy/install.py`
(`HEALTH_URL`), then install again.

Verified on 2026-11-05 on the workspace the app was built on (steps 1 to 3). Not yet verified on a second workspace.
