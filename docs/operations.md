# Operations

- **Restart:** `supervisorctl restart markdown-editor`. After pulling new code, run `deploy/install.py` again (it
  reinstalls and restarts). The app stops itself a minute after its last window closes and starts on the next visit
  (`stop_when_no_windows`), so STOPPED in `supervisorctl status` is normal.
- **Logs:** `/var/log/supervisor/markdown-editor-stderr.log` (every request, and any blocked page resource, logged as
  `Content-Security-Policy blocked`).
- **Earlier versions of a file:** `data/.apps/markdown-editor/history/<file name>-<id>/`, one file per save with the
  contents it replaced, newest 30 kept; `source.txt` in each folder names the original path. To restore one, copy it
  over the file (the page picks the change up within a few seconds).
- **"Changed outside the editor":** an agent or person wrote the file while the page had unsaved edits. "Load the new
  version" drops the page's edits; "Keep mine" writes the page's version over the outside one (which is kept in the
  history first).
- **A file opens read only:** it is not `.md`, `.markdown`, `.mdown`, `.mkd` or `.txt`, or the workspace user cannot
  write it.
- **Refused files:** anything outside `/home/user` (`MARKDOWN_EDITOR_ROOT`), anything under a `.secrets` folder, files
  over 5 MB, files that are not UTF-8 text.
- **Settings** (environment, in the program entry): `MARKDOWN_EDITOR_PORT` (8131), `MARKDOWN_EDITOR_ROOT`
  (`/home/user`), `MARKDOWN_EDITOR_SEARCH_ROOT` (`/home/user/workspace`, where the start page looks for files),
  `MARKDOWN_EDITOR_DATA_DIR` (`data/.apps/markdown-editor`).
- **Per-browser preferences** (local storage): the last mode chosen (Suggest unless changed), the name comments are
  signed with, the recently opened files.
