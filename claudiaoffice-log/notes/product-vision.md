# Claudia — product vision and design notes

Created 2026-11-02 from the owner's notes of that day; moved here 2026-11-05. The decisions taken are D58–D72 in
`decision-log.md`. This file keeps the reasoning and the owner's own pictures in one place. Where something is
Claude's proposal and not yet agreed, it says so.

## The idea in one paragraph

Claudia helps a person turn a thought into something others can judge, and keeps her thinking critically on the way.
Computes, composes and creates are three forms of one story: a model that simulates something, a text that explains
the background and what was found, a presentation that tells the arc from inspiration to insight. Users are not pushed
into one way of working, but moving between the forms must be truly easy, and the evidence must travel with the story.

## Design drivers (from the owner)

- **Stories across the suite.** A natural scientist or an accountant works something out in computes; the suite helps
  turn that into a summary write-up, or a plan for explaining the steps of thought. Someone writes a document in
  composes and wants to tell others; the suite helps turn the thoughts into a presentation in creates.
- **Critical thinking.** The story is told and developed critically, not just formatted nicely.
- **Goal, plan and work evolve together, with immediate feedback.** How does what I am doing fit the plan I made to
  reach my goal? Starting work can show that the plan must change; seeing the work can show that the goal must change.
  Design thinking is a source of ideas.
- **From a rough idea to something others can judge.** The owner often has a good idea but can only jot a few notes
  and a scribble, and gets stuck on how to represent it: convoluted, or not knowing where to start. If the software
  can help with that step, it is worth a lot.
- **No forced way of thinking.** Everything is optional; help is offered, and the user reflects on whether a
  suggestion makes sense before committing to it.

## Process help

Documents may go through phases. In composes: **draft** (a backlog list, notes), **writing**, **polishing**. Creates
gets the same kind of help — who the presentation is for, what it needs to achieve, how to structure it, how to build
it. The phases serve the "think" part of the suite and suit scientific users, public administration and schools.
Nobody is required to use them.

**Decided (D71):** goal, audience and phase are only suggestions and at most document metadata. A user does not have
to follow phases or always have a goal. The user is offered one option, *"What would you like to achieve with this
document?"*, and goal, process and phases are derived from the answer. Claude's earlier proposal of a mandatory brief
with a plan outline is dropped. What stays from that proposal: the stage is a logged command so the history shows
changes, and when the AI suggests a change and the user dismisses it, the dismissal is remembered for that document so
it does not nag.

## claudia composes

- A **Word stand-in** for polished documents: reports, letters, scientific and technical texts with formulas, meeting
  notes, drafting together. The tools and the AI help take a draft or a list of bullet points towards a polished
  version.
- **Flow is the default view.** The page view is a switch in the main editing window; there is no separate print
  dialog or overlay.
- **Styles first.** You mark something as a heading. Every marking or style difference serves a purpose the user can
  name. When a style is applied that has no name yet, the user is invited to name it, with a small hint that the name
  should say what it is for.
- **Suggestions and authorship.** Edits by the AI are suggestions to review. People's contributions in live work are
  immediate. Each contribution should be identifiable by author.
- **Thinking aids from the AI.** Spelling, word choice, complicated wording, language style; later structure, and
  whether the plot or flow is understandable. Summaries and content proposals on request. An outline view that can be
  rearranged, and side-by-side versions of a paragraph, also appeal.

## claudia creates

- **Templates and style definition come first**, as in LaTeX's separation of content and layout. Inspiration: Beamer.
  Few shapes, not a drawing program.
- **Better than PowerPoint's masters.** Slides come from a template. In PowerPoint one is often unsure where the slide
  in front of you was derived from, and is tempted to edit the page number or format the title on each slide
  separately. Claudia must avoid that.
- **Connected thoughts.** Prezi's idea of connectivity: a thought, or a link in a chain of thoughts, becomes a slide.
- **Storytelling and audience.** Who and what is the presentation for, how should it be structured to reach that
  audience, and how should the work itself be organised to reach the goal?
- **Thinking aids from the AI.** Cluttered slides, poor word choice, spelling, structure; design choices such as
  colour schemes from the stated purpose and goal, and fonts from the purpose.
- **Collaboration.** Track changes records objects added and removed and text edited in them. Marking a shape or text
  box, or a group, locks it for others.
- **Media and formats.** JPEG, SVG, GIF and other figure and image formats. Import and export of PPTX and the
  OpenDocument presentation format.
- **LaTeX formulas and Mermaid diagrams** in creates, as in the other two apps.

## Who it is for

Besides scientists and accountants: public administration and schools. The owner would like Claudia to contribute to
an open-source push for public organisations.

*A note from the 2026-11-05 review:* this audience is the one the product currently serves worst. Public bodies in the
EU usually have to meet WCAG 2.1 AA through EN 301 549, and the grid, the menus and the dialogs are not operable by a
screen reader or by keyboard alone (UX-01 to UX-05). The ambition and the state of the code are furthest apart here.

## Material between the apps (D72)

The person's client opens both documents and pulls a result — a chart, a range, a passage — into the other one as an
embedded item that remembers where it came from: document, server, range or chart, revision. When the source changes,
the author is asked whether to update; nothing changes on its own. No server reads another document by itself, which
keeps each document's passwords and keys separate.

## File formats (D70)

OpenDocument first (ODT, ODS, ODP), Microsoft formats second. Claudia's own zipped JSON format stays and is the only
one that carries history, users and chat.

## Proposed addition to the vision statement (not decided)

Keep the existing statement and add: *"The three apps work together: an insight found in a table can become an
explanation in a text and a story in a presentation, with the evidence and the reasoning still attached, and the
software helps the author question the story as well as tell it."*

## Where the open questions are

See "Open design questions" in `decision-log.md`. Answered: how apps exchange material (D72), where goal and plan live
(D71), the order of file formats (D70). Still open: claim-and-evidence links, how suggestions and the authorship view
work on the log, the naming of styles, the rendering of Mermaid and LaTeX, the slide template model, and what public
organisations need.
