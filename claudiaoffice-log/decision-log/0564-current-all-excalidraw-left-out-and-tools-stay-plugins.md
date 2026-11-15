---
id: D564
title: "Excalidraw is left out for now, and tools for containers stay plugins the administrator registers"
status: current
applies-to: all
date: 2026-11-15
round: "Rendered text containers: the screens (branch containers)"
supersedes: []
superseded-by: []
---

# D564 · Excalidraw is left out for now, and tools for containers stay plugins the administrator registers

**The first containers are LaTeX, Mermaid and Typst.** The owner does not want another server component now. The plugin layer (D391) already runs tools the administrator registers, outside the server's own code, so nothing was added to it.

**Open question to the owner.** "Tooling for the text-rendering-figures container should be outside the server" can mean that (the tools run as separate programs under the plugin layer, as built) or that rendering should run on another machine. If it is the second, the render service needs a remote mode.
