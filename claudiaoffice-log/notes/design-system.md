# Claudia — design system (website v1)

First draft, agreed with the product owner on 2026-11-02; moved here 2026-11-05. The promo site is the reference
implementation. Domain: **claudia-office.de**. Use this as the starting point for the Nuxt web client and the shells
so that all three look like one suite.

> **Note from the 2026-11-05 review.** The palette below is implemented in `web/app/assets/tokens.css`, and three of
> its derived tokens fail WCAG contrast where they are used for text and for form borders. See UX-04 in
> `bugtracker.md` for the measured ratios and the concrete replacement values. The palette itself is good; the
> derivations (`--muted` at 58% ink, `--line` at 14% ink) are the problem.

## 1. Character

Quiet, elegant, a little warm; "Think with your data." Linux native, open for all. Privacy first: no third-party
requests, fonts self-hosted, no CDN. Inspired by Bret Victor: show, don't decorate. Lowercase app names, and a
handwritten wordmark only for "claudia" itself.

## 2. Colour

| Token | Hex | Use |
|---|---|---|
| Ink | `#1F1A33` | text on light, dark panels, favicon tile |
| Iris | `#5B4BC4` | brand accent, links, the ai user, hero gradient |
| Mist | `#E7E1F4` | soft surfaces, light-on-dark text tint (`#E6E0F5`) |
| Paper | `#F7F3EC` | light text on dark, default page background |
| Rose | `#D6477A` | **composes** (writing); user colour "anna" in illustrations |
| Teal | `#13917F` | **computes** (tables); user colour "tobi" |
| Apricot | `#F2A057` | **creates** (presentations); highlight and curve colour; text on apricot is Ink |

Hover variants used on the site: link hover `#F7B576`, teal darker `#0F7D6E`. Hero gradient:
`linear-gradient(45deg, #1F1A33 8%, #5B4BC4 62%, #D6477A)`.

Page background options offered in the try-out picker (the final choice is still open): paper `#F7F3EC`, sand
`#E6DCCB`, mist `#E7E1F4`, lilac `#D3CCEB`, sage `#D7E3DD`, ink `#1F1A33` (dark; text flips to Paper).

Collaborator colours in the apps: each participant gets one colour, and the **ai user is Iris**. One ai user per
document.

Contrast rule as originally written: white or Paper text on Ink, Iris, Rose and Teal; Ink text on Apricot and light
surfaces. **This rule is right and the implementation does not follow it** — Rose and Teal are used as text *on white*
in the app, where they reach 4.17:1 and 3.90:1 (UX-04).

## 3. Typography (all OFL, self-hosted)

- **Sacramento** 400 — the wordmark "claudia" only, never for app names or UI.
- **Fraunces** 400/500 and 400 italic — headlines and numerals.
- **Inter** 400/500 — UI, body, buttons (sentence case), app names (lowercase).
- **JetBrains Mono** 400 — code, formulas, command history.

Base size on the site is viewport-relative (1.1vmax); for the apps use 14–15 px UI text.

## 4. Logos

The wordmark is Sacramento outlines in ink, with the fill replaced by `#F7F3EC` on dark backgrounds; the SVG source is
in the site archive, and the rendered wordmark is `Wordmark.vue` in the web app.

App icons are 64×64 with a rounded tile (rx 15) and a white glyph:

- **composes** — a pen nib and baseline on rose (`#D6477A`): a diamond nib `M32 11 L42 32 L32 46 L22 32 Z` in white,
  a rose circle at the centre, a rose stem down to the point, and a translucent white baseline at `y=52`.
- **computes** — an `=` with a wavy lower bar on teal (`#13917F`): a straight stroke at `y=24` and a cubic wave
  `M16 41 C24 33 30 49 38 41 C42 37 45 38 48 40`, both 5 wide with round caps.
- **creates** — a single slide with a circle cut-out on apricot (`#F2A057`): a white rounded rect at
  `x=13 y=19 w=38 h=26 rx=5` with an apricot circle at `(25, 32) r=5`.
- **Suite favicon** — an ink tile with three dots at `y=32`, `r=7`, in rose, teal and apricot at `x=19, 32, 45`.

Rules: keep the 64×64 tile shape and corner radius; one colour per app; no gradients on icons; the three-dot favicon
stands for the suite. Symbolic versions are still to be drawn (E5.5).

## 5. Layout and components (web)

- Horizontal, panel-based side-scrolling on the site. Every panel is no wider than the front page; panels step by
  their left edge.
- A fixed top bar: the wordmark top left; three app links with colour dots top right, the current app underlined.
- Round arrow bubbles sit on the border between two pages and glide page by page; a staggered fade and slide reveals
  content when a page comes into view; panel edges carry a soft inner shadow plus a hairline.
- Buttons: sentence-case Inter 500, primary filled and others outlined. Cards: a 1 px translucent outline, with the
  Linux card highlighted by a "native" tag.
- One page per app, each in its colour, each marked "in development".
- Dark "ink" panels for the ai and history illustration; the history panel lists commands as
  `user · command · argument · time` in JetBrains Mono with the user's colour dot, followed by the chat with `@ai`.
- Mobile (≤736 px): a vertical layout, with arrows and the background picker hidden.

## 6. Illustrations

Generated SVGs: `hero.svg` (a grid and rising curve with anna, tobi and ai selections), `chat.svg` (the history and
chat with the ai — **keep unchanged**), and one per app (1250×1000). Fonts are embedded base64 so they render via
`<img>`.

## 7. Open items

- The final page background colour; the try-out picker is temporary.
- Download links are placeholders until installers exist (WEB-02).
- Some app-page copy describes plans — Office file import and export, what-if sliders, background workers — and should
  be revised as features land (WEB-01).
- A trademark check for the name "Claudia": an unrelated open-source project of that name exists, and "Claude" is
  close (E11.3).
- The site source is generated by small Python scripts, which could be added to the repo.
- **Added 2026-11-05:** a dark scheme for every token, which does not exist at all (UX-05), and a contrast test in
  `scripts/` so the palette cannot regress silently (UX-04).
