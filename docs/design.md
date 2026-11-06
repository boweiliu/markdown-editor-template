# Design

`docs/decisions.md` has the reasons; this is how the pieces fit.

## Loading

The page asks the server for the file (`GET /api/file`), splits off YAML front matter (shown as a collapsed
Properties strip, written back untouched), and lexes the body with the editor's own `marked` instance. Top-level
tokens become blocks; each block is parsed on its own into editor nodes. Token types the editor has no faithful node
for (raw HTML, link definitions, footnotes) become source blocks, shown and edited as text. A fresh editor is made for
every load, so Undo never reaches into another file. After the load the page records each top-level node's JSON: that
is what "unchanged" is measured against.

## Saving

One second after the last edit (or on Ctrl+S) the page builds the file text: a longest-common-subsequence match of
the recorded nodes against the current ones finds every block that is still exactly as loaded, and those are written
from their original source text; the rest go through Tiptap's serializer (with suggestion and comment marks rendered
as CriticMarkup). The text is sent with the version (`base_sha256`) it was built on; the server refuses it with 409
if the file changed since, otherwise copies the old contents into the history and replaces the file atomically. If
the text equals what is on disk, nothing is written.

## Suggest mode

The `suggestChanges` plugin keeps the on/off state; a Tiptap `dispatchTransaction` hook passes each transaction
through `transformToSuggestionTransaction` when Suggest is on and the edit changes the document's text. Edits that
leave the text alone (formatting, lists, comments) pass through unchanged. Accept and reject use the plugin's own
commands. Suggestion marks are allowed on block nodes so a new list item or a deleted paragraph can be marked.

## CriticMarkup

One inline tokenizer reads all five forms; `{~~a~>b~~}` becomes a deletion and an insertion sharing one id, so they
are accepted or rejected together. On write, a deletion followed directly by an insertion is written back as a
substitution, spaces inside suggestion marks are protected from the serializer (which would otherwise move them
outside the mark), and the plugin's zero-width placeholders are removed.

## Watching for outside changes

Every 4 seconds (while the tab is visible) the page asks for the file's version. If it changed and the page has no
unsaved edits, the new version is loaded in place, keeping the scroll position; otherwise the page stops saving and
asks.

## Safety

Files outside `/home/user` (after resolving symlinks) and under any `.secrets` folder are refused. Only markdown and
text files are written. The page is served with a Content-Security-Policy that admits only its own scripts.
