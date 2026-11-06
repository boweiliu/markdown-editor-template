# Markdown Editor

An Imbue Studio template. To install it on a workspace, ask your agent: "Install the Markdown Editor from
https://github.com/boweiliu/markdown-editor-template" (it follows `skills/import-markdown-editor/SKILL.md`). MIT
licensed.

A Studio app for reading and reviewing the markdown files agents write: plans, notes, reports. It shows the file
formatted (headings, lists, tables, task lists, code), and by default it is in **Suggest** mode: what you type and
delete becomes tracked suggestions, and you can comment on any selection. Suggestions and comments are saved inside
the file in [CriticMarkup](https://criticmarkup.com), so the agent that reads the file next sees them in place:

```
Ship it on {==Friday==}{>>Sam: Monday? Friday is a holiday<<}. We {--might --}{++will ++}cut the old importer.
```

**Edit** mode changes the file directly, **Read** mode changes nothing. Accept or reject one suggestion by clicking it,
or all of them at once from the toolbar.

Saving is automatic. Blocks you did not touch are written back byte for byte, so the editor never reformats the parts
of an agent's file you did not edit. When an agent rewrites the file while it is open, the page shows the new version
(or, if you have unsaved edits, asks which to keep). Every save keeps the version it replaced.

## Open a file

- From the launcher: Markdown Editor, optionally with a File path.
- By link: `http://<app origin>/?path=/home/user/workspace/notes/plan.md` (add `&mode=edit` or `&mode=read` to
  override the saved mode). An agent can hand a person this link for any plan it writes.
- From the app's start page: type a path, or pick from the recently opened files or the markdown files in the
  workspace (newest first).

## How it works

A Flask server (`src/markdown_editor/`) reads and writes files under `/home/user` (never a `.secrets` folder; only
`.md`, `.markdown` and `.txt` are written; a save is refused when the file changed since the version it started from).
The page (`frontend/`, TypeScript, built with Vite into `src/markdown_editor/web/`, which is saved with the code so
installing needs no Node) is Tiptap 3 with its official markdown extension, plus the open
`@handlewithcare/prosemirror-suggest-changes` plugin for tracked changes. CriticMarkup is read by a custom tokenizer
and written by the marks' own markdown renderers. `docs/decisions.md` says why each piece was chosen.

| Part | Where |
| --- | --- |
| Server, file access, history | `src/markdown_editor/runner.py`, `files.py` |
| Editor setup, Suggest mode | `frontend/src/editor.ts` |
| CriticMarkup marks and tokenizer | `frontend/src/critic.ts` |
| Saving without reformatting | `frontend/src/blocks.ts`, `document.ts` |
| The page | `frontend/index.html`, `frontend/src/main.ts`, `styles.css` |
| Install on a workspace | `deploy/install.py`, `deploy/markdown-editor.conf` |

## Install, run, test

From the workspace root, with this repo cloned at `.external_worktrees/markdown-editor`:

```bash
python3 .external_worktrees/markdown-editor/deploy/install.py     # install or update, start, check
```

Tests (from the repo folder):

```bash
uv tool run --with flask --with pytest --with playwright --with-editable . pytest -q   # server and browser
cd frontend && npm ci && npx vitest run                                                  # editor and saving
```

Change the page: edit `frontend/src/`, then `cd frontend && npx vite build`, and save the rebuilt
`src/markdown_editor/web/` with the change. More in `docs/`: `setup.md`, `operations.md`, `design.md`,
`decisions.md`, `tests.md`.
