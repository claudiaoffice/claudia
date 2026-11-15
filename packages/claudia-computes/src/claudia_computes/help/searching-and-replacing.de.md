---
id: computes.searching-and-replacing
title: Wie finde und ersetze ich etwas in meiner Arbeitsmappe?
apps: computes
language: de
source-hash: 76d205f9b97a
tags: Suchen, Finden, Ersetzen, Muster, Baukasten, Treffer
explains: Suchen & Ersetzen, Ersetzen durch, Muster bauen, Ausgelassen
---
**Bearbeiten ▸ Suchen & Ersetzen…** (Strg+F) öffnet ein Feld neben dem Tabellenblatt. Geben Sie ein, was Sie suchen,
und die Zellen, die es enthalten, werden schon während der Eingabe markiert; die Eingabetaste springt zum nächsten
Treffer, Umschalt+Eingabetaste zum vorherigen. Strg+H öffnet dasselbe Feld, in dem **Ersetzen durch** schon zu sehen ist.

## Wo gesucht wird

Die Schaltfläche **Suchen in** sagt, was durchsucht wird: **Alles (3)** oder die Namen der Arten, die eingeschaltet
sind. Ein Druck darauf öffnet eine Liste mit einem Kontrollkästchen für jede Art und der Zahl ihrer Treffer: **Text**
(was Sie in eine Zelle eingegeben haben), **Formeln** (die Formel, wie sie geschrieben ist, mit ihrem `=`) und
**Werte** (was eine Zelle anzeigt, auch was eine Formel ausrechnet). **Alle** und **Keine** unten in der Liste
schalten jede Art ein oder aus. Die Auswahlliste daneben sagt, wie weit gesucht wird: **Dieses Tabellenblatt**,
**Alle Tabellenblätter** oder **Auswahl**; die Kontrollkästchen **Groß-/Kleinschreibung beachten** und **Ganze Zelle**
grenzen die Suche weiter ein.

## Das Feld verschieben

Ziehen Sie das Feld an seiner Titelleiste dorthin, wo es nicht verdeckt, woran Sie arbeiten. Es bleibt dort, bis Sie
die Seite neu laden. Mit der Tastatur verschieben **Alt+Pfeiltasten** das Feld (**Alt+Umschalt+Pfeiltasten** in
größeren Schritten; auf dem Mac die Wahltaste), außer der Cursor steht in einem Textfeld, wo diese Tasten ihre eigene
Bedeutung behalten. Jeder Dialog lässt sich genauso verschieben.

## Mehr als ein Wort beschreiben

**Muster bauen…** macht aus dem Feld Teile, die Sie zusammensetzen – „ein Buchstabe, dann eine oder mehrere Ziffern,
dann der Text `EUR`“ –, und ein Satz darunter sagt in einfachen Worten, was gefunden wird, damit Sie prüfen können, ob
es das ist, was Sie meinten. **Nur in Zellen, die…** stellt eine Bedingung an die ganze Zelle, zum Beispiel „enthalten
nicht `Entwurf`“. Zellen, die zu den Teilen passen, aber eine Bedingung nicht erfüllen, stehen unter **Ausgelassen**,
mit dem Grund – ein fehlender Treffer bleibt so nie ein Rätsel.

## Ersetzen

Schalten Sie **Ersetzen durch…** ein, und jeder Treffer zeigt, was aus ihm würde. Nehmen Sie das Häkchen bei denen weg,
die bleiben sollen, und drücken Sie dann **Diesen ersetzen** oder **Alle ersetzen**. Das Ganze ist ein Schritt im
Verlauf, „Rückgängig“ holt also jede Zelle zurück. Werte lassen sich nicht ersetzen – ein Wert folgt aus seiner
Formel –, und ein Ersatz, der eine Formel zerstören oder eine Zelle zu lang machen würde, wird übersprungen und sagt
das. Eine Zelle, die gerade jemand anderes bearbeitet, wird übersprungen, mit dem Namen der Person.

Um einen Teil des Gefundenen wiederzuverwenden, drücken Sie im Baukasten bei diesem Teil auf **Behalten** und klicken
dann im Ersatz auf seinen Namen: „die Ziffern behalten, den Text `EUR` in `USD` ändern“.

## Das Muster selbst schreiben

Wenn Sie Muster schreiben können, zeigt **⋯ ▸ Muster selbst schreiben…** das Muster, das der Baukasten gemacht hat,
zum Bearbeiten. Die Schreibweise ist die des Python-Moduls `re`. Ein Fehler wird in Worten erklärt, mit der Stelle, an
der er steht. Sobald Sie das Muster bearbeiten, kann der Baukasten es nicht mehr zeigen; **Zurück zum Baukasten** kehrt
zu dem zurück, was Sie vorher hatten.
