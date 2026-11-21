"""A scripted stand-in for the AI model in the text app (the real model is E3.6).

It reads the text with a small, readable set of wording rules (spelling, wordy phrases, "very", double spaces, long
sentences). For an asker in *suggest* mode it answers with suggestions, which people accept; in *act* mode it makes the
replacements itself, and what has no replacement (a long sentence) stays a remark (D262, D640). It says honestly when
it does not understand an instruction. It looks at the whole text, or at the paragraph the asker is in when they say
"this paragraph" / "here".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from claudia_composes import TextModel, TextRange

from .ai_mode import ACT
from .assistant import AiTurn, Call, Say, Task

LONG_SENTENCE_WORDS = 35  # more words than this in one sentence earns a remark
MAX_SUGGESTIONS = 20  # one instruction makes at most this many
_WORD = re.compile(r"\w+", re.UNICODE)
_SENTENCE = re.compile(r"[^.!?]+[.!?]*")
_REVIEW = re.compile(r"\b(review|check|proofread|edit|improve|suggest|polish|tighten|fix|look)\b", re.I)
_HERE = re.compile(r"\b(paragraph|here|cursor)\b", re.I)
_HELP = re.compile(r"^\W*(?:hi|hello|hey|help|what can you do)\b", re.I)

HELP = (
    "I am a stand-in for the real model and understand only a few things: say review (or check, proofread) and I "
    "suggest fixes for spelling, wordy phrases, 'very' and double spaces, and remark on very long sentences. "
    "Say 'check this paragraph' to look only at the paragraph you are in. In suggest mode I only suggest and you "
    "decide what is written; in act mode I make the fixes myself, and undo takes one back."
)
NOT_UNDERSTOOD = "I did not understand that: I am only a stand-in for the real model. Say help to see what I can do."
NOTHING = "I found nothing to suggest."

SPELLING = {
    "teh": "the",
    "recieve": "receive",
    "recieved": "received",
    "recieves": "receives",
    "recieving": "receiving",
    "seperate": "separate",
    "seperately": "separately",
    "occured": "occurred",
    "definately": "definitely",
    "accomodate": "accommodate",
    "untill": "until",
    "wich": "which",
}
WORDINESS = (
    ("in order to", "to", "“in order to” can almost always be “to”."),
    ("due to the fact that", "because", "“because” says the same in one word."),
    ("at this point in time", "now", "“now” says the same in one word."),
    ("a number of", "several", "“several” is shorter and as exact."),
    ("in the event that", "if", "“if” says the same in one word."),
    ("with regard to", "about", "“about” is plainer."),
    ("prior to", "before", "“before” is plainer."),
    ("utilize", "use", "“use” is plainer than “utilize”."),
    ("utilise", "use", "“use” is plainer than “utilise”."),
)


@dataclass(frozen=True)
class Finding:
    """One thing worth saying about a paragraph. ``replacement`` is ``None`` for a remark, ``""`` for a deletion."""

    start: int
    end: int
    replacement: str | None
    reason: str


def match_case(original: str, replacement: str) -> str:
    """``replacement`` with the capital letter ``original`` starts with: ("In order", "to") gives "To"."""
    if replacement and original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _spelling(text: str) -> list[Finding]:
    pattern = re.compile(rf"\b({'|'.join(SPELLING)})\b", re.I)
    return [
        Finding(
            m.start(), m.end(), match_case(m[0], SPELLING[m[0].casefold()]), f"Spelling: “{SPELLING[m[0].casefold()]}”."
        )
        for m in pattern.finditer(text)
    ]


def _wordiness(text: str) -> list[Finding]:
    return [
        Finding(m.start(), m.end(), match_case(m[0], replacement), reason)
        for phrase, replacement, reason in WORDINESS
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.I)
    ]


def _intensifiers(text: str) -> list[Finding]:
    found = []
    for m in re.finditer(r"\bvery\s+(?=\w)", text, re.I):
        before = text[: m.start()].rstrip()
        if before and not before.endswith((".", "!", "?")):  # at the start of a sentence it is left alone
            found.append(Finding(m.start(), m.end(), "", "“very” rarely adds meaning; a stronger word does."))
    return found


def _double_spaces(text: str) -> list[Finding]:
    return [
        Finding(m.start(), m.end(), " ", "One space between words.") for m in re.finditer(r"(?<=\S) {2,}(?=\S)", text)
    ]


def _long_sentences(text: str) -> list[Finding]:
    found = []
    for m in _SENTENCE.finditer(text):
        sentence = m[0].strip()
        words = len(_WORD.findall(sentence))
        if words > LONG_SENTENCE_WORDS:
            start = m.start() + len(m[0]) - len(m[0].lstrip())
            found.append(
                Finding(start, start + len(sentence), None, f"This sentence has {words} words. Consider splitting it.")
            )
    return found


def findings(text: str) -> list[Finding]:
    """What the rules find in one paragraph, in reading order; where two overlap the earlier one wins."""
    every = [*_spelling(text), *_wordiness(text), *_intensifiers(text), *_double_spaces(text), *_long_sentences(text)]
    kept: list[Finding] = []
    for item in sorted(every, key=lambda f: (f.start, f.end)):
        if not kept or item.start >= kept[-1].end:
            kept.append(item)
    return kept


class TextEngine:
    """Reads one instruction about a text and turns it into suggestions, or in act mode into edits."""

    def plan(self, task: Task) -> list[AiTurn]:
        """The steps for what the asker wrote."""
        text = task.text.strip()
        if _HELP.match(text):
            return [Say(HELP)]
        if not _REVIEW.search(text):
            return [Say(NOT_UNDERSTOOD)]
        model = task.document.model
        assert isinstance(model, TextModel)
        only = self._paragraph_of(task, model) if _HERE.search(text) else None
        acting = task.mode == ACT
        steps: list[Call] = []
        more = 0
        for paragraph in model.paragraphs:
            if only is not None and paragraph.id != only:
                continue
            for item in self._findings_in(model, paragraph.id, paragraph.text, acting=acting):
                if len(steps) >= MAX_SUGGESTIONS:
                    more += 1
                elif acting and item.replacement is not None:
                    steps.append(_written(paragraph.id, item))
                else:
                    steps.append(_suggested(paragraph.id, item))
        if not steps:
            return [Say(NOTHING)]
        return [*steps, Say(_report(steps, more))]

    @staticmethod
    def _findings_in(model: TextModel, paragraph: str, text: str, *, acting: bool) -> list[Finding]:
        """What the rules find in one paragraph. Suggesting, what is suggested already is left out; acting, every
        place counts (an open suggestion for it simply goes out of date) and the list runs from the paragraph's end,
        so that an edit never moves a place that is still to come."""
        if acting:
            return findings(text)[::-1]
        open_now = {
            (s.anchor.start, s.anchor.end, s.replacement)
            for s in model.suggestions.values()
            if s.state == "open" and s.anchor.paragraph == paragraph
        }
        return [item for item in findings(text) if (item.start, item.end, item.replacement) not in open_now]

    @staticmethod
    def _paragraph_of(task: Task, model: TextModel) -> str | None:
        hold = task.document.presence.of(task.sender)
        for region in hold.regions if hold else ():
            if isinstance(region, TextRange) and any(b.id == region.paragraph for b in model.paragraphs):
                return region.paragraph
        return None


def _focus(paragraph: str, item: Finding) -> tuple[dict, ...]:
    return (TextRange(paragraph, item.start, item.end).to_data(),)


def _suggested(paragraph: str, item: Finding) -> Call:
    params: dict = {"paragraph": paragraph, "start": item.start, "end": item.end, "reason": item.reason}
    if item.replacement is not None:
        params["replacement"] = item.replacement
    return Call("suggest", params, _focus(paragraph, item))


def _written(paragraph: str, item: Finding) -> Call:
    params = {
        "paragraph": paragraph,
        "start": item.start,
        "end_paragraph": paragraph,
        "end": item.end,
        "text": item.replacement,
    }
    return Call("replace_text", params, _focus(paragraph, item))


def _report(steps: list[Call], more: int) -> str:
    """What it says when it is done: how many places it changed or suggested, and what is left."""
    changed = sum(1 for step in steps if step.method == "replace_text")
    suggested = len(steps) - changed
    parts = []
    if changed:
        parts.append(f"I changed {changed} place{'s' if changed != 1 else ''}; undo takes a change back.")
    if suggested:
        parts.append(
            f"I made {suggested} suggestion{'s' if suggested != 1 else ''}; nothing is changed until you accept one."
        )
    if more:
        parts.append(f"There are {more} more: ask me again after you went through these.")
    return " ".join(parts)
