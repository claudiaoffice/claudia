---
id: computes.pivot-tables
title: Wie fasse ich eine Tabelle mit einer PivotTable zusammen?
apps: computes
language: de
source-hash: ea42ece8008f
tags: Pivot, PivotTable, Zusammenfassung, gruppieren, Summe, Anzahl, Mittelwert, Bericht, xlsx, ods
explains: PIVOT, SQL
---
Eine PivotTable rechnet eine Tabelle für Sie zusammen. Sie legen fest, wonach an der Seite gruppiert wird (die
Zeilen), wonach oben (die Spalten) und was addiert wird (die Werte), und die PivotTable gibt für jedes Paar eine Zahl
an. Sie ist immer aktuell: Ändert sich die Tabelle, ändert sich die PivotTable mit, und es gibt nichts zu
aktualisieren.

## Beispiel

Eine Tabelle namens `Sales` mit der Region in Spalte A, dem Quartal in Spalte B und dem Betrag in Spalte C:

```
      A         B         C
1   Region    Quartal   Betrag
2   Nord        Q1        100
3   Nord        Q2        150
4   Süd         Q1         80
5   Süd         Q2        120
```

Wählen Sie **Werkzeuge ▸ PivotTable…** (Strg+Alt+V), lassen Sie `Sales` als Quelle stehen und klicken Sie auf Anlegen.
Haken Sie im Feldbereich `Region`, `Quartal` und `Betrag` an und legen Sie `Region` in Zeilen, `Quartal` in Spalten und
`Betrag` in Werte:

```
      A                 B         C         D
1   Summe von Betrag  Quartal
2   Region              Q1        Q2       Gesamt
3   Nord                100       150       250
4   Süd                  80       120       200
5   Gesamt              180       270       450
```

Die erste Zelle enthält `=PIVOT("SalesPivot")` und füllt die Zellen um sich herum. Sie können diese nicht
überschreiben: Ändern Sie die PivotTable in ihrem Feldbereich oder ändern Sie die Quelle.

## Was Sie ändern können

- **Wohin ein Feld kommt.** Ziehen Sie seinen Chip in ein anderes Feld, oder öffnen Sie sein Menü ▾ und wählen Sie
  *Verschieben nach …*; das geht auch mit der Tastatur. Eine PivotTable hat ein Zeilenfeld und ein Spaltenfeld; legen
  Sie ein zweites in ein volles Feld, geht das erste zurück in die Liste.
- **Wie ein Wert gerechnet wird.** Mit **Werkzeuge ▸ Wertfeldeinstellungen…** (Strg+Umschalt+Alt+U) wählen Sie Summe,
  Anzahl, Mittelwert, Minimum oder Maximum und benennen den Wert um.
- **Filter.** Ein Feld in Filter behält nur die Elemente, die Sie wählen (sein Menü ▾, *Elemente wählen…*).
- **Summen.** Mit den Schaltern *Gesamtzeile* und *Gesamtspalte* im Feldbereich schalten Sie jede ein oder aus.
- **Die Abfrage.** **PivotTable als SQL anzeigen…** zeigt die Abfrage, die die PivotTable ausführt. *In SQL-Abfrage
  umwandeln…* macht daraus ein gewöhnliches `SQL()`-Ergebnis mit denselben Zahlen; das ist ein Schritt, den Sie
  rückgängig machen können.
- **Entfernen.** **PivotTable löschen…** entfernt die PivotTable und die Zellen, die sie gefüllt hat.

## In anderen Programmen

Eine PivotTable wird in `.xlsx`- und `.ods`-Dateien als PivotTable gespeichert, mit ihren Zahlen in den Zellen; Excel
und LibreOffice öffnen sie daher als solche. Excel erstellt sie beim Öffnen der Datei neu. Eine PivotTable in einer
Datei, die Sie öffnen, kommt als lebendige PivotTable herein, wenn Claudia aus derselben Quelle genau dieselben Zahlen
bekommt; sonst bleiben die Zellen gewöhnliche Zellen, und der Importbericht nennt die PivotTable als nicht gelesen.
Für das Gruppieren von Datumswerten, „Werte anzeigen als“, berechnete Felder, Datenschnitte, PivotCharts oder eine
Quelle außerhalb der Arbeitsmappe gibt es noch keine PivotTable in Claudia: Sie bleiben in der Datei, wie sie sind,
sind hier aber nicht lebendig.

## Wenn es nicht klappt

- Die Tabelle ist leer: Legen Sie ein Feld in Werte; der Feldbereich sagt es.
- `#SQL!` oder ein anderer Fehler in der ersten Zelle: Der Feldbereich sagt in der Zeile unter seinen Feldern, welcher,
  zum Beispiel dass ein Feld nicht mehr in der Quelle ist.
- „Ihre Zelle wurde überschrieben, daher zeigt sie nichts“: Etwas hat die erste Zelle ersetzt. Löschen Sie die
  PivotTable und legen Sie sie neu an.
- „Es gibt keine Tabelle namens … (mehr)“: Die Quelle wurde gelöscht. Wählen Sie mit *Ändern…* unter Quelle eine
  andere.
