---
id: computes.writing-a-formula
title: Wie schreibe ich eine Formel?
apps: computes
language: de
source-hash: b8895d08df45
tags: Formel, Zelle, Bezug, Grundlagen
explains: =, SUM, Formelleiste
---
Eine Formel beginnt mit `=`. Geben Sie sie in eine Zelle oder in die Formelleiste über dem Raster ein und drücken Sie die Eingabetaste.

Eine Formel kann Zahlen, Text in Anführungszeichen, die vier Grundrechenarten (`+ - * /`), Bezüge auf andere Zellen
(`A1`, `B2`), Zellbereiche (`A1:A10`) und Funktionen (`SUM(A1:A10)`) enthalten. Klicken Sie eine Zelle an, statt ihren
Bezug zu tippen: Während Sie eine Formel schreiben, fügt ein Klick auf eine Zelle (oder ein Auswählen mit den
Pfeiltasten) oder das Ziehen über einen Bereich dessen Bezug an der Cursorposition ein.

## Beispiel

Mit 10 in `A1` und 20 in `A2` ergibt `=A1+A2` in `A3` nach der Eingabetaste 30. Ändert sich `A1` später auf 15,
rechnet `A3` von selbst neu und zeigt 35 – genau darum geht es bei einer Formel: Sie ist nicht die Zahl selbst,
sondern der Weg dorthin.

## Eine Funktion finden

Tippen Sie den Anfang eines Funktionsnamens in die Formelleiste (`=SU`), und seine Signatur samt kurzem Beispiel
erscheint gleich dort. So müssen Sie die Zelle nicht verlassen, um nachzusehen, was die Funktion braucht. Die
vollständige, durchsuchbare Liste aller Funktionen finden Sie im Hilfebereich auf dem Reiter „Dokumentation“.

## Wenn es nicht funktioniert

- `#VALUE!`: Ein Argument hat nicht die Art von Wert, die die Funktion erwartet (zum Beispiel Text, wo eine Zahl nötig war).
- `#REF!`: Ein Bezug zeigt außerhalb des Blatts, oft weil eine Zeile oder Spalte gelöscht wurde, von der er abhing.
- `#DIV/0!`: Es wurde durch null geteilt, auch durch eine leere Zelle als Divisor.
- Eine Formel, die als Text statt als Ergebnis erscheint: Sie beginnt nicht mit `=` – Claudia behandelt den Inhalt
  einer Zelle nur dann als Formel, wenn er damit beginnt.
