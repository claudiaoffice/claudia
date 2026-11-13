---
id: typeset.configure-latex
title: Wie richte ich LaTeX ein, damit Formeln und Textblöcke gesetzt werden?
apps: composes, computes, creates
language: de
source-hash: 26a9c3642a4a
tags: latex, xelatex, pdftocairo, Formeln, Satz, miktex, texlive, mactex, poppler, Installation, Pfad
explains: xelatex, pdftocairo, Tools > Check LaTeX
---

Claudia wird ohne LaTeX geliefert. Sie installieren es einmal, wie jedes andere Programm, und sagen Claudia, wo es liegt.
Zwei Programme sind nötig: `xelatex` (es setzt den Text) und `pdftocairo` (es macht aus dem Ergebnis ein Bild).

*Entwurf:* Der Satzdienst nimmt die beiden folgenden Einstellungen an und kann sie prüfen. Der Einstellungsbildschirm,
die Serveroption, die sie ausfüllt, der Menüeintrag *Tools > Check LaTeX* und die Anmeldung der Schriften Ihrer
TeX-Installation folgen mit der Anbindung an den Server; bis dahin übergibt ein Administrator die Einstellungen im Code.

## Schritte

1. **Eine TeX-Distribution installieren.**
   - Windows: MiKTeX oder TeX Live.
   - macOS: MacTeX oder das kleinere BasicTeX. BasicTeX fehlen einige Pakete; fügen Sie sie in Schritt 3 hinzu.
   - Linux: Ihre Paketverwaltung, zum Beispiel unter Debian oder Ubuntu
     `sudo apt install texlive-xetex texlive-latex-extra texlive-fonts-recommended`.
2. **`pdftocairo` installieren.** Es gehört zu *poppler*, das unter Windows und macOS ein eigenes Programm ist.
   - Windows: zum Beispiel `scoop install poppler` oder `choco install poppler`.
   - macOS: `brew install poppler`.
   - Linux: `sudo apt install poppler-utils`.
3. **Sicherstellen, dass die Pakete da sind.** Claudia braucht `standalone`, `fontspec`, `unicode-math`, `amsmath` und
   `amssymb`. Mit TeX Live oder MacTeX: `sudo tlmgr install standalone fontspec unicode-math amsmath amsfonts`
   (unter Windows ohne `sudo`, und in einer Konsole mit Administratorrechten, wenn TeX Live für alle Benutzer installiert ist).
4. **Nur MiKTeX: das Nachinstallieren im Hintergrund abschalten.** Öffnen Sie die MiKTeX-Konsole, *Einstellungen*,
   *Allgemein*, und stellen Sie die Installation fehlender Pakete auf *Nie*. Ein Satzauftrag läuft ohne Netzwerk und hat
   nur Sekunden; ein Download mittendrin würde ihn abbrechen. Installieren Sie stattdessen die Pakete aus Schritt 3 in der MiKTeX-Konsole.
5. **Claudia sagen, wo die Programme liegen.** Für jede der beiden Einstellungen `xelatex` und `pdftocairo` können Sie angeben
   - den vollständigen Pfad des Programms,
   - den Ordner, in dem es liegt (Claudia sucht dort dann das richtige Programm), oder
   - nur den Namen, wenn sein Ordner im PATH des Servers liegt; das bewirkt auch eine leere Einstellung.
6. **Prüfen.** Führen Sie `xelatex --version` und `pdftocairo -v` in einer Konsole aus. Claudias eigene Prüfung (*Tools >
   Check LaTeX*) testet jedes Programm, die Schriften und eine kleine Formel und sagt, welcher Schritt fehlgeschlagen ist und was zu tun ist.

## Beispiel

Unter Windows können die Einstellungen mit einem nur für einen Benutzer installierten MiKTeX und mit scoop installiertem
poppler so aussehen. Die Ordner sind typisch; Ihre können abweichen, schauen Sie auf die letzte Seite des Installationsprogramms
oder suchen Sie nach `xelatex.exe`.

```
xelatex     = C:\Users\Sam\AppData\Local\Programs\MiKTeX\miktex\bin\x64
pdftocairo  = C:\Users\Sam\scoop\apps\poppler\current\Library\bin
```

Unter macOS mit MacTeX und Homebrew muss nichts eingestellt werden, wenn `/Library/TeX/texbin` und `/opt/homebrew/bin` im PATH
des Servers liegen. Wird der Server aus der Desktop-App gestartet und sieht sie nicht, stellen Sie ein:

```
xelatex     = /Library/TeX/texbin
pdftocairo  = /opt/homebrew/bin
```

## Wenn es nicht funktioniert

- *„xelatex was not found on the PATH“*: Stellen Sie `xelatex` wie in Schritt 5 ein oder legen Sie seinen Ordner in den PATH
  und starten Sie den Server neu.
- *„The folder … has no xelatex in it“*: Sie haben einen Ordner angegeben, aber das Programm liegt in einem Unterordner.
  Bei TeX Live liegt es in `bin/<System>`, bei MiKTeX in `miktex/bin/x64`.
- *„File `x.sty' not found“*: Ein LaTeX-Paket fehlt. Installieren Sie es wie in Schritt 3 (`tlmgr install x` oder die
  MiKTeX-Konsole). *Check LaTeX* nennt das Paket.
- *„The font … is not available on this server“*: Der Schriftkatalog enthält kein Latin Modern. Fügen Sie die Latin-Modern-Schriften
  Ihrer TeX-Installation (in deren Ordner `fonts`) dem Schriftkatalog hinzu; das gehört zur Anbindung an den Server.
- Unter Windows verzögern Virenscanner `xelatex` manchmal beim ersten Start; der zweite Versuch ist schnell.

Claudia führt LaTeX mit ausgeschaltetem *Shell-Escape* und in einem eigenen Ordner aus, sodass eine Formel keine Programme
ausführen und Ihre Dateien nicht lesen kann. Das ist keine Garantie gegen jeden Angriff; führen Sie den Satz auf einem
Server, den viele Personen teilen, in einem Container aus.
