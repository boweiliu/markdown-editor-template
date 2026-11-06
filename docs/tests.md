# Tests

From the repo folder:

```bash
uv tool run --with flask --with pytest --with playwright --with-editable . pytest -q
cd frontend && npm ci && npx vitest run
```

- `tests/test_files.py`, `tests/test_runner.py`: file access rules (outside the root, symlinks out, `.secrets`,
  read-only kinds, binary files), save with version check and history, the file list, every route. Each test works in
  its own temporary folder; the real workspace is never touched.
- `tests/test_browser.py`: the page in Chromium against a server on a spare port and a temporary folder: opening
  changes nothing, Suggest is the default, typing at the end of a wrapped paragraph saves only the new words as an
  insertion, a signed comment, Accept all, an outside change shows up, Read mode cannot edit. Skipped when no Chromium
  is found (`MARKDOWN_EDITOR_CHROMIUM`, default the Studio workspace's `/opt/fortress/tilion-fortress/tilion`).
- `frontend/src/document.test.ts`: the editor in jsdom: byte-for-byte round trip of a file with front matter, HTML,
  tables, odd list markers and no final newline; only the edited block rewritten; Suggest-mode insertions,
  deletions and new paragraphs; CriticMarkup read, accepted and rejected; comments; formatting applied directly;
  block boundaries after deletes and inserts.
- `frontend/src/corpus.test.ts`: with `MD_CORPUS=<file listing paths>`, opens every listed file and checks it saves
  back byte for byte. On 2026-11-05 it passed over the 1,472 markdown files of the workspace it was built on
  (`find data docs .agents -name '*.md'`). Skipped without `MD_CORPUS`.
