---
id: computes.summing-with-a-condition
title: Wie addiere ich nur die Zeilen, die eine Bedingung erfüllen?
apps: computes
language: de
source-hash: 9948498374a0
tags: sumif, countif, Kriterium, Bedingung, Summe
explains: SUMIF, COUNTIF, SUMIFS
---
`SUMIF` addiert die Zahlen eines Bereichs, aber nur dort, wo ein anderer Bereich ein Kriterium erfüllt:
`SUMIF(zu prüfender Bereich, Kriterium, zu addierender Bereich)`. `COUNTIF` zählt statt zu addieren. Ein Kriterium ist
ein Wert, der übereinstimmen soll, oder Text wie `">15"`, `"<>erledigt"` oder `"nord*"` (das `*` steht für beliebigen Text).

## Beispiel

```
      A            B
1   nord          10
2   süd           20
3   nord          30
```

`=SUMIF(A1:A3, "nord", B1:B3)` ergibt 40: Es addiert `B1` und `B3`, die Zeilen, in denen `A` gleich `"nord"` ist.
`=COUNTIF(B1:B3, ">15")` ergibt 2: `B2` und `B3` sind größer als 15.

Brauchen Sie mehrere Bedingungen gleichzeitig? `SUMIFS` nimmt Paare aus einem Bereich und seinem Kriterium, alle in
derselben Form wie der Bereich, der summiert wird: `=SUMIFS(B1:B3, A1:A3, "nord", B1:B3, "<25")` ergibt 10 – nur `B1`
liegt in den Nord-Zeilen *und* unter 25.

## Wenn es nicht funktioniert

- `#VALUE!`: Die Bereiche haben nicht alle dieselbe Form (gleich viele Zeilen und Spalten).
- Ein Kriterium in Anführungszeichen, das mit einem Vergleich beginnt (`">15"`), gilt als Vergleich und nicht als
  Text – um eine Zelle zu finden, die buchstäblich mit `>` beginnt, gibt es heute keine Möglichkeit; formulieren Sie den Vergleich um.
- Verglichen wird immer der eigene Wert der Zelle; `SUMIF`/`COUNTIF` werten den Kriterienbereich nie als Formel aus.
