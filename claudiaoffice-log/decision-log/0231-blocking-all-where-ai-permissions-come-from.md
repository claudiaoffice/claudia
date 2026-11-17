---
id: D231
title: "Where the AI's permissions come from"
status: blocking
applies-to: all
date: 2026-11-10
round: "Open design questions"
supersedes: []
superseded-by: []
---

# D231 · Where the AI's permissions come from

**Where the AI's permissions come from:** the intersection of the AI's role and the asker's (E7.4); fairness, cancellation and queue visibility in the AI server; structured output for small local models.

*Carried over on 2026-11-10 from the decision log's "Open design questions" section, which had no numbers. Nothing here is decided yet, and the owner marked it blocking on 2026-11-10.*

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** The first question is settled by D261 and built: each request runs under `Account.acting_for` (`assistant.py`), the weaker role of the AI and the asker, narrowed to the asker's mode. Of the rest, the runner is first in, first out across documents and can cancel (`claudia_ai.runner`); a visible queue position, fairness beyond FIFO and structured output for small models are not built. Kept as the owner marked it.
