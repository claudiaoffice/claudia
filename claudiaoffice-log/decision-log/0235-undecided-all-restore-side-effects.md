---
id: D235
title: "Side effects of D51/D52 to settle elsewhere"
status: undecided
applies-to: all
date: 2026-11-10
round: "Open design questions"
supersedes: []
superseded-by: []
---

# D235 · Side effects of D51/D52 to settle elsewhere

**Side effects of D51/D52 to settle elsewhere:** redaction has to reach hidden lines, or a secret removed from the active line stays in the file; viewers must not see hidden lines; chat is not rolled back by a restore; after a restore the `ai` user must rebuild its context.

*Carried over on 2026-11-10 from the decision log's "Open design questions" section, which had no numbers. Nothing here is decided yet.*

*2026-11-16: the first point is settled by D724 (steps on hidden lines can be redacted, and the stored file is rewritten, D725). The others stay open.*

*2026-11-19: the second point, chat, is settled by D1307 (chat is not rolled back by a restore). Still open: viewers must not see hidden lines, and the `ai` user must rebuild its context.*
