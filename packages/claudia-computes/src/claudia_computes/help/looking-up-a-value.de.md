---
id: computes.looking-up-a-value
title: Wie suche ich einen Wert in einer Tabelle?
apps: computes
language: de
source-hash: cde9ec4a8c33
tags: Suchen, Nachschlagen, Tabelle, xlookup, vlookup, match
explains: XLOOKUP, VLOOKUP, MATCH
---
`XLOOKUP` sucht einen Wert in einer Zeile oder Spalte und gibt den passenden Wert aus einer anderen zurück:
`XLOOKUP(was gesucht wird, wo gesucht wird, wo die Antwort steht)`. Es ersetzt das ältere `VLOOKUP` und verlangt weder,
dass die beiden Bereiche nebeneinander liegen, noch dass die Suchspalte die erste ist.

## Beispiel

Eine kleine Tabelle mit Schulungskosten, mit der Kategorie in Spalte A und den tatsächlichen Ausgaben in Spalte C:

```
      A            B          C
1   Kategorie    Geplant     Ist
2   Reisen        12.000      9.450
3   Schulung       3.000      2.750
```

`=XLOOKUP("Schulung", A2:A3, C2:C3)` ergibt 2.750: Es sucht `"Schulung"` in `A2:A3` und gibt den Wert daneben aus
`C2:C3` zurück. Wird nichts gefunden, ergibt `XLOOKUP` `#N/A`, es sei denn, Sie geben als viertes Argument einen
Ersatz an: `=XLOOKUP("Werbung", A2:A3, C2:C3, "nicht geplant")` ergibt `"nicht geplant"`.

`MATCH("Schulung", A2:A3, 0)` gibt stattdessen die *Position* zurück – 2, denn „Schulung“ ist die zweite Zelle des
Bereichs. Das brauchen Sie, wenn Sie die Zeilennummer selbst möchten oder sie an `INDEX` weitergeben wollen.

## Wenn es nicht funktioniert

- `#N/A`: Der Wert wurde nicht gefunden, und es wurde kein viertes Argument als Ersatz angegeben.
- `#VALUE!`: Die beiden Bereiche, die Sie `XLOOKUP` gegeben haben, sind nicht gleich lang oder jeweils nicht eine einzelne Zeile oder Spalte.
- Groß- und Kleinschreibung sowie Leerzeichen am Anfang oder Ende spielen bei Text keine Rolle, eine genaue Zahl muss aber genau übereinstimmen.
