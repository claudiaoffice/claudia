# Penpot design file

`claudia.penpot` is the design system and screens of Claudia as one Penpot file (import it in Penpot).
`generator/` builds it from the running web app (`node build.mjs out/full.penpot`; needs the server running for text measuring).

Pages: Foundations, Icons, Components, Front page, **Dialog components**, **Styles dialog**, **Search & replace**.

The file is hand-corrected in Penpot, so a rebuild never replaces it. Add new pages to it with
`python3 generator/tools/extend.py out/full.penpot claudia.penpot out/new.penpot "Page" ...`:
it only adds pages, components, text styles and tokens that the file lacks, and leaves everything else as it is.
