# Questions the drafts layouts.feature and templates.feature raise

Each has the default I wrote the scenarios for; cross out or change what you do not want.

1. **Wording of the strip.** "Update layout · n slides instead", "New layout from this slide", "Undo" (the words of the
   mock). *Default: as mocked.*
2. **Can an administrator add a template straight from Save as template…?** The scenarios have Save as template write a
   file that goes to the administrator (so that anyone can contribute), and an administrator adds it under Server
   settings. *Default: yes, as written. An administrator who saves a template could get a second button "Add to this server" later; not in this story.*
3. **Hint text of an empty placeholder** is its purpose ("Title"). *Default: the purpose.*
4. **Provisional layout name** is the parent's name and a number ("Two lists 2"), like a style deviation (D75, D309).
   *Default: as written.*
5. **When is the preview skipped?** For one slide only. *Default: as written.*
6. **How many layouts does the basic template have?** One, without placeholders. A template with real layouts (title, title and list, two lists…) comes with a separate decision (Q19: only the basic one ships for now). *Default: as written.*
7. **Where the scenarios run.** All with `@app:creates`; the desktop clients show the same page, so one `@desktop` scenario covers them. *Default: as written.*
8. **Change theme… lists the themes of the templates on the server** (there is no library of themes of their own, Q4). *Default: as written.*
9. **Not in these files:** pasting between decks (E10.25), pptx/odp masters and layouts (E10.24).
