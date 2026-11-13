---
id: render.configure-tools
title: How do I set up the tools behind formulas, diagrams and typeset pages?
apps: composes, computes, creates
language: en
tags: typst, mermaid, mmdc, chrome, latex, tools, plugins, rendered text, diagram, install, path, administrator
explains: tools.typst.path, tools.mmdc.path, tools.mmdc.chrome, Insert > Rendered text
---

A *rendered text* object keeps the text you write and shows a picture made from it: a LaTeX formula, a Mermaid
diagram or a Typst page. The pictures are made on the server by programs the administrator installs; Claudia does
not ship them. A document still opens and prints on a server that lacks a program, with the picture it had last.

## Steps

1. **Install what you want to offer.**
   - *Typst*: download the `typst` program, or `brew install typst`, or `winget install Typst.Typst`.
   - *Mermaid*: `npm install -g @mermaid-js/mermaid-cli` gives the `mmdc` program. It also needs Chrome or
     Chromium on the server.
   - *LaTeX*: see "How do I set up LaTeX" (`typeset.configure-latex`).
2. **Tell the server where they are** (only needed when a program is not on the PATH), in the server settings under
   `render.tools`. A tool is a path, or a path with options:
   `typst: /opt/typst/typst` and `mmdc: {path: /usr/local/bin/mmdc, chrome: /usr/bin/google-chrome, browser_args: [--no-sandbox]}`.
3. **Start the server.** Its start-up lines list the container types on offer and any that cannot be used, with the
   reason. A tool that is missing is reported when someone first uses it, so installing it later needs no restart.
4. **Add your own types (optional).** Put a manifest (a `.json` file, data only) in the `plugins` folder of the
   server's state folder, or the one named by `render.plugins_dir`. A manifest can only use tools you registered in
   step 2; it can never run a program of its own choosing.

## Good to know

- Rendering runs in a sandbox with limits on time, memory and output, and a picture is checked before it is used.
- To place a rendered picture in PowerPoint or OpenOffice files, the server turns it into a PNG with `rsvg-convert`
  (librsvg). Without it the picture is written as SVG and some programs show it badly.
