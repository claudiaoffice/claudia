# BITV 2.0 scorecard and the quick fixes on `bitv` (2026-11-13)

Asked for by the owner: a scale rather than pass or fail, split by aspect, weighed against the people affected. An
**estimate from reading the code and the QA log**. No screen reader was run; nothing here replaces a BIK BITV-Test. D233
(the accessibility standard) is still undecided: this note proposes, it does not decide.

**Update, same day:** the grid structure (UX-02) and alt text with decorative objects (UX-31) are now built on `bitv`; see
`bitv-grid-and-alt-text-2026-11-13.md`. The scores below are not re-estimated.

## How the number is made

BITV 2.0 points to EN 301 549, which takes in WCAG 2.1 A and AA. The BIK BITV-Test rates each test step *fulfilled*,
*rather fulfilled*, *partly*, *rather not* or *not fulfilled* (100, 75, 50, 25, 0 percent) and weights steps 3, 2, 1; 90
points or more counts as accessible. Conformance is stricter than the score: every step must be at least *rather
fulfilled*. This estimate rates 20 key WCAG criteria the same way and groups them by the four BITV principles. Criteria
with no evidence (use of colour alone, reflow, text spacing, hover content, pointer gestures) are **not in the score**.

| Principle | Today | Grid structure done | What costs the points |
|---|---|---|---|
| Perceivable | 58 | 67 | grid has no structure (UX-02); charts without a text alternative; the website blocks zoom (UX-07) |
| Operable | 62 | 77 | Tab trap and no region keys (fixed here, UX-29); drags with the mouse only; no skip link; title (fixed, UX-30) |
| Understandable | 62 | 62 | no page language (fixed here, UX-28) |
| Robust | 50 | 75 | grid cells without roles or names; no announcements of other people's or the `ai`'s changes |
| **Overall** | **59** | **70** | |

The figures are before the quick fixes on `bitv`. Re-scoring what they changed (page language 0 to 100, skip and region keys
75 to 100, title 50 to 75, contrast 75 to 100, the grid's Tab trap 25 to 75, since it stays a trap while a cell is edited)
gives about **71** overall; with the grid structure done as well, about **79**. The grid is what stands between the
product and 90.

## Who it is for

Germany, end of 2025: 7.8 million severely disabled people (9.4 %); of the most severe disability 10 % arms or legs, 9 %
spine and trunk, 4 % blindness or visual impairment, 4 % hearing, balance or speech, 16 % mental or emotional, 9 %
cerebral, 19 % not stated (Destatis, 2026). Of working age, 3.1 million could work and 1.12 million do (BIH, 2023). Not in
those counts: mild visual impairment, ageing, temporary injury. Colour vision deficiency: about 8 % of men, 0.4 % of women.
Dyslexia: estimates run from about 5 % to over 10 %.

| Group | Barrier today | Weight |
|---|---|---|
| Keyboard only, motor, speech input | Tab trap (fixed), mouse-only resizing and moving (open), no skip (fixed) | blocker for some, friction for many: first |
| Low vision, colour vision, ageing | contrast residue (fixed), zoom, colour alone (not assessed) | most people, mostly friction |
| Cognitive and learning | consistency between the apps (UX-22, UX-23), clear errors | friction; consistency work counts here |
| Blind, screen reader | the grid (UX-02), live updates, chart alternatives | few people, total blocker in computes: second, and the largest single gain |
| Deaf, hard of hearing | nothing: no audio | negligible |

## Order

1. Quick fixes (done on `bitv`): page language, document titles, F6 and Shift+F6, the contrast guard.
2. The accessible grid, with live announcements and a text alternative for charts (UX-02). Waits for the computes work in flight.
3. Keyboard alternatives for resizing and moving objects, then audits of colour use, reflow, text spacing, label in name.
4. Assistive technology on all three engines (Orca with WebKitGTK, NVDA with WebView2, VoiceOver with WKWebView), then an
   external BIK BITV-Test for a figure that can be quoted.

## What the quick fixes did, and left

Test first, as always: `web/tests/tokens.test.ts`, `regions.test.ts`, and additions to `i18n.test.ts`, `shell-bridge.test.ts`
and `shortcuts.test.ts` failed before the code. `web/e2e/regions.cjs` passes in headless Chrome (the system's, not the project's Chrome for Testing);
**Firefox was not tried**.

- **Contrast (UX-04).** The QA note's suggested apricot would have reached only 4.49:1 on its own soft tint, and computes'
  teal was 4.36:1 there; both `--app-dark` values moved a shade (the brand colours `--teal`, `--rose`, `--apricot` did not).
- **Language (UX-28), title (UX-30), F6 (UX-29).** See the bugtracker. F6 is a window-level shortcut with no menu entry,
  so no manifest or native menu changed; it shows in Config ▸ Shortcuts, whose labels are not translated today (as before).
- **Not done.** UX-07: the website is not in this repository. The grid structure. F6 inside a cell being edited. The
  desktop shells were not run; they show the same page, so they get the change with the next web build.
