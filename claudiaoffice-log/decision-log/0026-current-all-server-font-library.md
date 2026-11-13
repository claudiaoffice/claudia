---
id: D26
title: "font library"
status: current
applies-to: all
date: 2026-11-01
round: "Common to all three apps"
supersedes: []
superseded-by: []
---

# D26 · font library

A **font library** lives on the server as a service shared by the three servers: the OS fonts plus downloadable collections. A document declares the fonts it needs; the server delivers fonts the client lacks.

**Notes.** Built as `claudia-fonts`; not yet wired to the server. Fonts are served from our own server, never a CDN.
