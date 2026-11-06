# Decisions

What was decided while building the Markdown Editor, and why. Newest decisions are added at the end. The brief: a
viewer and editor for the markdown files agents hand to people (plans, notes, reports), where the default is to
comment and suggest changes rather than edit directly, built on an existing editor library rather than hand-rolled.
Every decision was made without a round of questions and is recorded here instead.

## 1. Editor library: Tiptap 3, not Milkdown

Compared on 2026-11-05 (GitHub stars, npm downloads per week, last push, license):

| Library | Stars | npm/week | Markdown | Tracked changes | Notes |
| --- | --- | --- | --- | --- | --- |
| Tiptap 3 (`@tiptap/core`, `@tiptap/markdown`) | 39.0k | 35M core, 6.2M markdown | official extension since v3, built on `marked`, custom tokenizers per extension | paid Pro add-on only; open ProseMirror plugins work | headless ProseMirror wrapper, biggest ecosystem |
| Milkdown 7 (`@milkdown/kit`, `crepe`) | 12.0k | 0.8M | native (remark round trip) | none | the library first proposed; smaller community |
| Lexical (`lexical`, `@lexical/markdown`) | ~22k | 8.5M | transformer based, lossy on anything unrecognised | none | not ProseMirror, so none of the ProseMirror tracked-change plugins apply |
| BlockNote | 10.4k | 1.0M | documented as lossy | none | block (Notion) model, MPL license |
| MDXEditor | 3.7k | 2.0M | good (mdast) | none | built on Lexical, React only |
| Plate | 16.7k | n/a | via remark | paid | React, shadcn bound |
| Vditor | 11.4k | 0.05M | good | none | Typora style, mostly Chinese-language community |
| Toast UI Editor | 18.0k | n/a | good | none | last push 2024-08, effectively unmaintained |
| Novel | 16.5k | n/a | via Tiptap | none | a Tiptap preset, last push 2025-01 |

The deciding requirement: suggest (redline) mode as the default. No free markdown editor ships tracked
changes. The best open implementation found is `@handlewithcare/prosemirror-suggest-changes` (MIT, 156k npm/week,
pushed 2026-08), which works on any ProseMirror editor. That rules out Lexical, MDXEditor and Plate (not ProseMirror)
and leaves Tiptap and Milkdown. Tiptap wins on community size (3x the stars, 40x the downloads), maintenance pace,
an official markdown extension whose tokenizers are pluggable per extension (needed for the redline syntax below),
and ready extensions for tables, task lists and links. Milkdown's remark round trip is more faithful in principle,
but decision 3 makes the editor's serializer matter much less, which removes Milkdown's main advantage.

No React: the page is plain TypeScript over Tiptap's core, bundled with Vite. Fewer moving parts, smaller bundle.

## 2. Where redlines and comments live: inside the file, as CriticMarkup

Suggestions and comments are written into the markdown file itself in CriticMarkup, the established plain-text
convention for tracked changes in markdown (criticmarkup.com):

- `{++inserted++}`, `{--deleted--}`, `{~~old~>new~~}` (a replacement)
- `{==highlighted text==}{>>the comment<<}`, or a bare `{>>comment<<}`

Why: the readers who matter most are agents. An agent that reads the plan file sees the person's suggestions and comments
in place, with no app, API or side file to know about. The cost is that the file carries the marks until someone
accepts or rejects them; Accept all and Reject all make that one click, and an agent can do the same with a text
replace. A separate notes file was rejected because agents would only see feedback if told where to look.

Comments carry an optional author prefix (`{>>Sam: ...<<}`) from a "Sign comments as" setting, so an agent can tell
human comments from its own.

## 3. Saving never rewrites what was not edited

Rich-text editors re-serialize the whole file on save, which reformats list markers, wrapping, escapes and anything
the editor does not model. Agents and git diffs suffer from that. So the file is split into top-level blocks (using
the editor's own `marked` lexer, whose tokens carry their exact source text), each block is parsed on its own, and on
save every block whose content is unchanged is written back byte for byte from the original source. Only edited or new
blocks go through the serializer. Opening and closing a file without edits never writes it at all.

Blocks the editor cannot represent faithfully (raw HTML blocks, link reference definitions, anything `marked` returns
that the schema has no node for) become a "source block": shown as monospace source, editable as text, written back
verbatim. YAML front matter is kept aside and written back untouched, shown as a small "Properties" strip.

## 4. Modes: Suggest (default), Edit, Read

- **Suggest** (default, saved per browser): typing and deleting become tracked insertions and deletions; comments can
  be added. Formatting changes (bold, headings) are applied directly, because CriticMarkup has no way to write a
  tracked formatting change and an untracked-but-saved change is better than one that silently disappears on reload.
- **Edit**: changes go straight into the file.
- **Read**: nothing can change; comments and suggestions still show.

Accept and reject work per suggestion (click it) or for the whole file.

## 5. A standalone app, not a change to the built-in Files app

Files is a built-in app shared by every workspace; changing it means an upstream change reviewed by the Studio team
(and an agent-built change to it would need careful review). A standalone app ships today, can be installed from
its own repo, and can be proposed upstream later once it has been used. Files' "open a
file" message handler takes every file with no per-extension filter, so the app does not try to take it over;
instead it opens any file by `?path=`, has a launcher entry with a Path parameter and a recent-files list, and an
agent can link `http://<app origin>/?path=/home/user/workspace/...` directly.

## 6. Saving and outside changes

Saving is automatic (one second after the last keystroke), so there is no Save button to forget; the header says
Saved / Saving / Unsaved. Every write carries the hash of the version it was based on; if the file changed on disk
in between (an agent rewrote the plan), the server refuses and the page offers Reload or Keep mine. While the page has
no unsaved changes it checks the file every few seconds and reloads on its own when an agent updates it.

The raw file is always one click away (Source view), and Download gives the file as it is on disk.

## 7. Files the app may open

Any file under `/home/user` the workspace user can read, which matches what the Files app already exposes. Only
`.md`, `.markdown` and `.txt` are written; anything else opens read-only as source.

## 8. A wrapped paragraph that is edited comes out as one line

Agents often hard-wrap paragraphs at a fixed width. In markdown those line breaks read as spaces, and the editor has
to hold them as spaces: with real newlines left in the text, typing at the end of a wrapped paragraph made the browser
report the whole paragraph as replaced, and Suggest mode then recorded the entire paragraph as deleted and retyped
(found while testing, 2026-11-05). So an edited paragraph is written as one line; every paragraph that was not edited
keeps its wrapping exactly (decision 3). Re-wrapping to the old width was rejected: it would guess at a width and make
the change look bigger than it is.

## 9. Every save keeps the version it replaced

Before each save the server copies the file's previous contents to `data/.apps/markdown-editor/history/`, the 30
newest per file. A bug in the editor can therefore never cost more than one save, and an agent or person can always
get yesterday's plan back. It costs a few kilobytes per save.

## 10. What CriticMarkup cannot express is applied, not lost

A suggested paragraph break or join, and a suggested formatting change, have no CriticMarkup form. The paragraph break
is written as a plain break (the new paragraph's text is still marked as inserted), and formatting is applied directly
(decision 4). After a rejection, paragraphs left empty are removed, because markdown cannot hold an empty paragraph.
