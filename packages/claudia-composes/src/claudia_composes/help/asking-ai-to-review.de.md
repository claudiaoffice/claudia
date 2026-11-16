---
id: composes.asking-ai-to-review
title: Wie bitte ich die KI, meinen Text zu prüfen?
apps: composes
language: de
source-hash: e65949173ce8
tags: KI, Assistent, Prüfen, Vorschläge, Chat
explains: "@ai, Vorschläge"
---
Jedes Dokument kann einen KI-Benutzer haben, der im Chat der Werkzeugleiste wie jede andere Person erscheint. Tippen Sie
`@ai` und danach, was Sie möchten, genauso, wie Sie `@maria` schreiben, um die Aufmerksamkeit einer Kollegin zu bekommen.

Was er mit dem macht, was er findet, hängt vom Schalter über dem Reiter „Verlauf & Chat“ ab, den Sie in jedem Dokument
für sich selbst setzen. Im Modus *Vorschlagen* schlägt er nur vor: Jeder Vorschlag wird dort angezeigt, wo er gilt;
übernehmen Sie ihn, um die Änderung vorzunehmen, oder lassen Sie ihn, dann bleibt er für später offen. Im Modus
*Handeln* nimmt er die Korrekturen selbst vor, und jede ist ein Schritt im Verlauf, den Rückgängig zurücknimmt.

## Mit einem Sprachmodell

Hat der Server ein Sprachmodell, bitten Sie in Ihren eigenen Worten: `@ai straffe den zweiten Absatz`, `@ai füge eine
Überschrift für die Ergebnisse hinzu`, `@ai prüfe die Rechtschreibung dieses Absatzes`. Er sieht den Absatz, in dem Ihr
Cursor steht. Im Modus *Handeln* formuliert er Wörter um, fügt Absätze hinzu und gibt Absätzen eine Formatvorlage,
liest dann, was er geändert hat, und korrigiert sich; im Modus *Vorschlagen* bietet er dieselben Änderungen als
Vorschläge an.

## Was er ohne Sprachmodell versteht

Ohne Sprachmodell antwortet ein einfacher Platzhalter, der nur wenige englische Wendungen versteht:

- `@ai review this text` (oder `check`, `proofread`, `edit`, `improve`, `polish`, `tighten`, `fix`, `look`) liest das
  ganze Dokument und schlägt Korrekturen für Rechtschreibung, umständliche Formulierungen, „very“ und doppelte
  Leerzeichen vor und weist auf Sätze hin, die sehr lang geworden sind.
- `@ai check this paragraph` (oder `here`, oder die Erwähnung von „the cursor“) beschränkt dieselbe Prüfung auf die
  Stelle, an der Ihr Cursor gerade steht, statt auf das ganze Dokument.
- `@ai help` (oder `hi`, `hello`, `hey`, oder die Frage, was er kann) antwortet mit einer kurzen Erinnerung daran, was er versteht.
- Alles andere bekommt ein ehrliches „I did not understand that“ statt einer Vermutung.

Der Assistent versteht derzeit englische Anweisungen.

## Beispiel

Schreiben Sie einen Absatz mit einem Tippfehler und einem langen, abschweifenden Satz und senden Sie dann
`@ai review this text`. Im Modus Vorschlagen antwortet der Assistent im Chat, wie viele Vorschläge er gemacht hat, und
jeder erscheint an genau den Wörtern, um die es geht – als Durchstreichung mit Ersatz für eine Formulierungskorrektur
oder als bloße Bemerkung bei etwas wie einem langen Satz, den er nicht für Sie beheben kann. In Ihrem Dokument ändert
sich nichts, bis Sie einen Vorschlag übernehmen. Im Modus Handeln ist der Tippfehler sofort behoben, und der lange Satz
bekommt trotzdem eine Bemerkung.

## Warum Sie wählen

Der KI-Benutzer von Claudia ändert über genau dieselben Methoden wie ein Mensch, sodass er nie etwas tun kann, das
ein Mensch nicht ebenfalls rückgängig machen könnte. Ob Sie seine Lesart des Textes zuerst als zweite Meinung wollen
oder als Änderung, die Sie zurücknehmen können, entscheiden Sie – im Text, in der Tabelle und in den Folien gleich.
