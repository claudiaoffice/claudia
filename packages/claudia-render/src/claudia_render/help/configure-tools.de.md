---
id: render.configure-tools
title: Wie richte ich die Programme hinter Formeln, Diagrammen und gesetzten Seiten ein?
apps: composes, computes, creates
language: de
source-hash: 95a25b7cd9b4
tags: typst, mermaid, mmdc, chrome, latex, Programme, Plugins, gerenderter Text, Diagramm, Installation, Pfad, Administrator
explains: tools.typst.path, tools.mmdc.path, tools.mmdc.chrome, Einfügen > Gerenderter Text
---

Ein Objekt *Gerenderter Text* behält den Text, den Sie schreiben, und zeigt ein Bild, das daraus gemacht wird: eine
LaTeX-Formel, ein Mermaid-Diagramm oder eine Typst-Seite. Die Bilder entstehen auf dem Server mit Programmen, die die
Administratorin oder der Administrator installiert; Claudia liefert sie nicht mit. Ein Dokument lässt sich auch auf
einem Server öffnen und drucken, dem ein Programm fehlt, und zeigt dann das Bild, das es zuletzt hatte.

## Schritte

1. **Installieren Sie, was Sie anbieten möchten.**
   - *Typst*: das Programm `typst` herunterladen, oder `brew install typst`, oder `winget install Typst.Typst`.
   - *Mermaid*: `npm install -g @mermaid-js/mermaid-cli` liefert das Programm `mmdc`. Zusätzlich braucht es Chrome
     oder Chromium auf dem Server.
   - *LaTeX*: siehe „Wie richte ich LaTeX ein" (`typeset.configure-latex`).
2. **Sagen Sie dem Server, wo sie liegen** (nur nötig, wenn ein Programm nicht im PATH ist), in den Servereinstellungen
   unter `render.tools`. Ein Werkzeug ist ein Pfad oder ein Pfad mit Optionen:
   `typst: /opt/typst/typst` und `mmdc: {path: /usr/local/bin/mmdc, chrome: /usr/bin/google-chrome, browser_args: [--no-sandbox]}`.
3. **Starten Sie den Server.** Seine Startzeilen nennen die angebotenen Containertypen und alle, die nicht benutzbar
   sind, mit dem Grund. Ein fehlendes Programm wird gemeldet, sobald jemand es zum ersten Mal braucht; eine spätere
   Installation braucht also keinen Neustart.
4. **Eigene Typen ergänzen (optional).** Legen Sie eine Manifestdatei (`.json`, nur Daten) in den Ordner `plugins` im
   Zustandsordner des Servers oder in den, den `render.plugins_dir` nennt. Ein Manifest darf nur Werkzeuge benutzen,
   die Sie in Schritt 2 eingetragen haben; es kann nie ein Programm eigener Wahl starten.

## Gut zu wissen

- Das Rendern läuft in einer Sandbox mit Grenzen für Zeit, Speicher und Ausgabe; ein Bild wird geprüft, bevor es
  verwendet wird.
- Damit ein gerendertes Bild in PowerPoint- und OpenOffice-Dateien steht, macht der Server mit `rsvg-convert`
  (librsvg) ein PNG daraus. Ohne es wird das Bild als SVG geschrieben, und manche Programme zeigen es schlecht.
