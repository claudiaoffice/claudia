# E10.31 Save as Template to the server: architecture

Proposal of 2026-11-25. Story: `Projects/claudia-office/_tasks/e10.31-save-as-template-to-the-server.md`. Mocks O–S:
`mockups/creates-templates-save-to-server.svg`. Diagram: `mockups/creates-template-library-architecture.svg`.

## What the code has (read on 2026-11-25)

* `TemplateLibrary` (`claudia_server/template_library.py`) already `check`s, `add`s (`added_by`), `remove`s and refuses a taken name.
  The file it keeps is written afresh with the adder as its `exporter`, so who added a template is already in the file, but
  `Listed` does not carry it.
* `GET /api/templates` (every person who may make documents) lists; the administrator's page (`admin_templates.py`) adds and
  removes. A person has no way to add or remove.
* `save_as_template` is a wire method inside a deck, recorded as an export (`leaves="export"`); `ctx.template_library()` gives a
  method the server's library and `ctx.user` the person.
* File ▸ New (`OpenDialog.vue`) runs before any document is open, so it only has HTTP.

## Where each piece goes, and why there

| Piece | Goes in | Why there |
|---|---|---|
| `added_by`, `added_at` on `Listed`; `replace(id, data, by)` | `template_library.py` | the library owns the folder and the ids; replace keeps id and place and writes the file in one step |
| `add_to_templates(name, purpose, language, replace=None)` | `template_methods.py` | the deck is where the template file is made (`template_file`); the file need not travel to the client and back; no `leaves="export"`, because nothing leaves the server |
| `DELETE /api/templates/{id}` for the adder; `added_by`, `added_at`, `mine` in the listing | `template_routes.py` | File ▸ New has no document, so it can only speak HTTP, as it already does to list and to start a deck |
| *Added by* and *Added* columns | `admin_templates.py`, `AdminTemplates.vue` | the same data, for the administrator who may remove any |
| library log lines (added, replaced, removed, by whom) | the server's log, next to the administrator's | a library event belongs to the server, not to a document's history |
| two buttons, name-taken states | `SaveTemplateDialog.vue` | the dialog of mock O and P |
| Remove on own cards, one shared confirmation | `OpenDialog.vue`, new `RemoveTemplateDialog.vue` used by `AdminTemplates.vue` too | the confirmation exists once in the administrator's page; extracting it avoids a second copy |
| `removeTemplate`, `addedBy`, `mine` | `web/app/lib/templates.ts`, `slide-session.ts` | the libs own the calls; components stay thin |

## To confirm in the first TDD step

* How `may_make(request)` gives the signed-in name to the router (the administrator's routes have it; the people's routes have only
  the yes or no). If it does not, the router gets a `who(request)` the way `address_of` is passed.
* That the log of the server has a place for library events that is not the administrator's audit of settings.

## Seams proposed

1. `TemplateLibrary` (unit): add, replace, remove, names, who added. 2. The wire method and the routes against a real library
(taken name, replace of someone else's refused, remove of someone else's refused, administrator removes any). 3. The pure parts of
`templates.ts` (vitest). 4. One browser E2E for the @core scenarios (add, find under New, replace, remove).
