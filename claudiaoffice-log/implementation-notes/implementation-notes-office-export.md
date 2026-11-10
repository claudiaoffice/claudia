# Word, Excel and PowerPoint export, and pictures in a pptx (D212, D213)

## Where this came from

The work was done on a local copy of `xlsx-docx-pptx-additive-io` whose content matched `04a779c` ("Setup of
testing library … XLSX version") plus these changes, and which had diverged from the remote branch. Meanwhile the
remote branch was merged into `main` (#23) and `main` moved on, so the local copy could no longer be pulled or pushed. On 2026-11-10 its 23 changed files were
re-applied on top of `main` with `shapes-n-images` (D209–D211) already merged, as one commit that the remote branch
fast-forwards to.

What was changed on the way in:

* **Decision numbers.** The local branch cited "D205" (export) and "D206" (pictures), neither recorded in the log;
  both numbers belong to computes' charts on `main`. They are D212 and D213 now.
* **pptx colours.** The local branch also taught `_rgb` to read `rgba()` and dropped the opacity, and resolved
  roles with `resolve_css` inside `slides_to_pptx`. `shapes-n-images` had fixed the same bug better (`_look`,
  flattening over the palette's `page`, D211), so only the picture branch of `slides_to_pptx` was kept.
* **Menus.** `main` had grown Help and Format menus and chart dialogs in the same three workspace files; the new
  `'export-format'` dialog was added next to them rather than replacing anything.
* **`uv.lock`** was re-resolved (the local copy had been written by a newer uv, `revision = 5`), `po/claudia.pot`
  regenerated, `export_office` added to `vulture_whitelist.py`, and claudia-server bumped to 0.21.0.

## The shape of it

One RPC per app, all named `export_office`, each accepting exactly the one format its app can write. The server
does the conversion with the app's own `*_io` package and `office_export.py` wraps the bytes as base64, because the
protocol is JSON text frames. The web client's `ExportFormatDialog` lists the formats a workspace hands it; an
option with `local` (composes' Markdown) is built in the browser, any other asks the server and saves the answer
with `downloadBase64`.

File ▸ Download became Claudia's own JSON snapshot in all three apps, and File ▸ Manage ▸ Export… the office
formats. That retires D123's disabled Download stubs in computes and creates.

## Pictures

`slides_to_pptx` writes an image object with `add_picture(BytesIO(asset.data), …)` at the object's box. The
tests build a tiny valid GIF through the real `decode_image`, so python-pptx has a header to read. Import stays
one-sided (D213): a picture in a pptx is beyond-claudia content until decoding embedded pictures into an
`ImageAsset` is built.

## Still open

* Import of pictures from pptx (above), and of images in docx and xlsx.
* `export_office` sends the whole file in one frame; a very large deck with many pictures will want a streamed or
  chunked answer.
