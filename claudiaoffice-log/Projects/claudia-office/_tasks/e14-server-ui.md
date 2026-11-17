---
pm-task: true
projectId: "[[claudia-office|claudia-office]]"
parentId:
id: "2ld3kmwjmw369o69"
title: "E14 Server UI"
type: "task"
status: "in-progress"
priority: "medium"
start: "2026-11-05"
due: ""
progress: 60
assignees: []
tags: []
subtaskIds: []
dependencies: []
createdAt: "2026-11-05T06:36:12.321Z"
updatedAt: "2026-11-17T18:00:00.000Z"
customFields:
  y349wfjfmw2k7pty: "ALL"
---

As a user, I need a number of centralized services on the server that cannot meaningfully integrated into the apps of compose, create and compute:

- a page that allows me to see all documents I have been involved with, as an owner, an editor or viewer
- access to the font library of the server: downloading and managing new font (sets)
- centralized settings e.g. for the latex integration and other config options
- a way to switch between the three applications fluently, so I can open each app from the server start page.

Before we start coding, let's first make designs in SVG or PNG that we can discuss before settling on a UI.

**2026-11-16:** the font library part is proposed as a fourth server settings page, Fonts: `notes/e3-3-font-management-ui.md`, `notes/mockups/fonts-1-server-settings.svg`, `fonts-2-add-fonts.svg`.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Three of the four wishes are built: Server settings has pages for the AI model, typesetting (the LaTeX and tool paths), access and documents, and fonts (`AdminApp.vue`, `AdminTypesetting.vue`, `AdminFonts.vue`; E3.11, E3.13 f, D1041); one server hosts the three apps and its front page lists and opens the documents of every app (E3.12, D430, D444). Partly: *Mine* lists the documents this browser or shell opened (`lib/mine.ts`), not every document a person is involved with, which the server cannot know without the documents' passwords.

Project: [[claudia-office|claudia-office]]
