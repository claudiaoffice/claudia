---
id: typeset.configure-latex
title: How do I set up LaTeX so that formulas and text blocks are typeset?
apps: composes, computes, creates
language: en
tags: latex, xelatex, pdftocairo, formulas, typesetting, miktex, texlive, mactex, poppler, install, path
explains: xelatex, pdftocairo, Tools > Check LaTeX
---

Claudia does not come with LaTeX. You install it once, like any other program, and tell Claudia where it is.
Two programs are needed: `xelatex` (it typesets) and `pdftocairo` (it turns the result into a picture).

*Draft:* the typesetting service accepts the two settings below and can check them. The settings screen, the
server option that fills them in, the menu entry *Tools > Check LaTeX* and the registration of the fonts of your
TeX installation arrive with the server wiring; until then an administrator passes the settings in code.

## Steps

1. **Install a TeX distribution.**
   - Windows: MiKTeX or TeX Live.
   - macOS: MacTeX, or the smaller BasicTeX. BasicTeX lacks some packages; add them in step 3.
   - Linux: your package manager, for example on Debian or Ubuntu
     `sudo apt install texlive-xetex texlive-latex-extra texlive-fonts-recommended`.
2. **Install `pdftocairo`.** It is part of *poppler*, which is a separate program on Windows and macOS.
   - Windows: for example `scoop install poppler` or `choco install poppler`.
   - macOS: `brew install poppler`.
   - Linux: `sudo apt install poppler-utils`.
3. **Make sure the packages are there.** Claudia needs `standalone`, `fontspec`, `unicode-math`, `amsmath` and
   `amssymb`. With TeX Live or MacTeX: `sudo tlmgr install standalone fontspec unicode-math amsmath amsfonts`
   (on Windows leave out `sudo`, and use a console with administrator rights if TeX Live is installed for all users).
4. **MiKTeX only: turn off installing on the fly.** Open the MiKTeX Console, *Settings*, *General*, and set the
   installation of missing packages to *Never*. A typesetting job runs without a network and has only seconds;
   a download in the middle of it would stop it. Install the packages from step 3 in the MiKTeX Console instead.
5. **Tell Claudia where the programs are.** For each of the two settings `xelatex` and `pdftocairo` you can give
   - the full path of the program,
   - the folder it is in (Claudia then looks for the right program there), or
   - just the name, if its folder is on the PATH of the server; this is also what an empty setting does.
6. **Check.** Run `xelatex --version` and `pdftocairo -v` in a console. Claudia's own check (*Tools > Check
   LaTeX*) tests each program, the fonts and a small formula, and says which step failed and what to do about it.

## Example

On Windows, with a MiKTeX that was installed for one user only and poppler installed with scoop, the settings
may look like this. The folders are typical; yours can differ, look in the installer's last page or search for
`xelatex.exe`.

```
xelatex     = C:\Users\Sam\AppData\Local\Programs\MiKTeX\miktex\bin\x64
pdftocairo  = C:\Users\Sam\scoop\apps\poppler\current\Library\bin
```

On macOS with MacTeX and Homebrew, nothing needs to be set if `/Library/TeX/texbin` and `/opt/homebrew/bin` are on
the PATH of the server. If the server is started from the desktop app and does not see them, set

```
xelatex     = /Library/TeX/texbin
pdftocairo  = /opt/homebrew/bin
```

## When it does not work

- *"xelatex was not found on the PATH"*: set `xelatex` as in step 5, or put its folder on the PATH and restart
  the server.
- *"The folder … has no xelatex in it"*: you gave a folder, but the program is in a sub-folder. On TeX Live it is
  in `bin/<system>`, on MiKTeX in `miktex/bin/x64`.
- *"File `x.sty' not found"*: a LaTeX package is missing. Install it as in step 3 (`tlmgr install x`, or the
  MiKTeX Console). *Check LaTeX* names the package.
- *"The font … is not available on this server"*: the font catalogue has no Latin Modern. Add the Latin Modern
  fonts of your TeX installation (in its `fonts` folder) to the font catalogue; this is part of the server wiring.
- On Windows, antivirus programs sometimes delay `xelatex` at its first start; the second try is quick.

Claudia runs LaTeX with *shell escape* off and in a folder of its own, so a formula cannot run programs or read
your files. This is not a guarantee against every attack; on a server shared by many people, run the typesetting
in a container.
