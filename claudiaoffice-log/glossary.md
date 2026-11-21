<goal of this file>
Build shared notions and contexts
</goal of this file>

<rules>
- get approval from the owner for any new context or notion you put in here.
- same for any change to this file.
</rules>

<format of this file>
Entries follow this format:

# {Context name}

{one or two sentence description of what this context is and why it exists}

## Language

**Notion 1**
{a one or two sentence description of the term}
_avoid_: put here other words that one might use for the same thing, and that could lead to confusion

**Notion 2**
{description}
_avoid_: 

</format of this file>

<start>

# claudia

The shared language of the claudia office suite: what people work on, who works on it, and how a document's history is kept. Shared by all three apps.

## Language

### Documents

**Document**
The sealed whole that people create, share and open: its content, its history, its chat and its people, belonging to one app.
_avoid_: file, container, doc

**App**
One of claudia composes, claudia computes and claudia creates; every document belongs to exactly one app.
_avoid_: module, app type, product

**Page**
One piece of paper a document is laid out on, in page view or when printed, in any app.
_avoid_: sheet

**Sheet**
A grid of cells in a computes document.
_avoid_: worksheet, spreadsheet, tab

**Slide**
One page of a creates document, shown in turn when presenting.
_avoid_: page, foil

**File format**
The kind of file a document is imported from or downloaded as: claudia's own, OpenDocument or MS Office.
_avoid_: format (on its own), file type

### Servers

**Server**
The claudia software that keeps documents for people to open, hosting all three apps.
_avoid_: host, backend, instance

**Administrator**
The person who looks after a server; never a role in a document, and sees that documents exist but not what is in them.
_avoid_: admin, owner

**Setup code**
A short code that a server without an administrator shows only to someone who can read its own log or files; whoever types it names the server's first administrator. It is never sent over the network and dies once the first administrator is named.
_avoid_: setup password, activation code, token, pin

**Access secret**
A secret a server may ask for before it lists or makes documents; it does not open any document, and an administrator sets and removes it.
_avoid_: server password, api key, document password

**Exposed server**
A server that can be reached from other computers: it listens on a non-loopback address or sits behind a proxy.
_avoid_: public server, remote server, internet server

**Reset of the administrators**
Removing all administrators of a server by starting it in a special way, which only someone with access to the server's machine can do; documents and settings stay, and new administrators can then be named. It is how access is regained when no administrator can sign in.
_avoid_: reset, factory reset, password reset

### Finding documents

**Place**
A location where claudia documents are kept: a server, as a person knows it by name and address. "This computer" is the claudia server running on her own machine; a claudia file in a folder on a disk is not in a place.
_avoid_: location, library, folder, storage

**Mine**
The documents a person has opened before, on any place; kept on her own client, never seen by a server.
_avoid_: recent, my documents, history

**Collection**
A named group of documents a person makes, from any places; kept on her own client, never seen by a server. A document may be in several collections.
_avoid_: folder, library, project

**Keyword**
A word on a document's cover that helps find it.
_avoid_: tag, label, category

### People

**User**
Anyone with a name in a document's list of people: a person or ai.
_avoid_: account, member, participant

**Person**
A human user.
_avoid_: account, member

**ai**
The one non-human user of a document; it acts within the rights of the person who asked it.
_avoid_: assistant, bot, agent, AI user

**Role**
What a user may do in one document: owner, editor or viewer. The administrator of a server is not a role.
_avoid_: permission, access level, admin (for owner)

**Presence**
Where each user is in a document right now, shown to the others; it is never stored.
_avoid_: cursor, awareness

**Lock**
A part of a document a user holds for a while, so that nobody else changes it there; it is never stored.
_avoid_: hold, reservation

**Author**
The user who made a step; a step made by accepting a proposal has the accepting person as its author.
_avoid_: writer, creator

### Security

**Sealed**
Readable only by a document's users, with their own keys, wherever the file is. A document is always sealed; only what is exported is not.
_avoid_: encrypted, locked

**Part**
One of the sealed parts of a document (its content, its history, its chat), each with a key of its own; a viewer can read only the content.
_avoid_: domain, section, layer

**Key slot**
One user's way into a document: opened by her name and password, it holds the keys to the parts her role may read. The recovery key has one too.
_avoid_: account, login

**Password**
What one person chose for one document; with her name, it unlocks that document. Nobody else, the server included, can show it.
_avoid_: account password, credentials

**Unlock**
To give one's name and password, or the recovery key, so that a sealed document opens for oneself, with the rights of one's role.
_avoid_: log in, sign in, authenticate

**Recovery key**
A key shown once, when a document is made or the key is made anew, that unlocks the document as an owner and lets someone who forgot her password choose a new one. Whoever holds it can read the document.
_avoid_: master password, backup key

**Cover**
What can be read of a sealed document without unlocking it: its title, description, keywords, app and times. It is what lets a place list documents.
_avoid_: manifest, metadata, details

**Download**
A sealed copy of a document for one person to keep: an owner gets the whole document, anyone else only her own key slot and the parts her keys open.
_avoid_: save as, export

**Export**
A copy of a document that anyone can read, in claudia's open export or another file format. Only an owner may include the history and chat, and every export goes into the exit record.
_avoid_: download, save as

**Exit record**
The sealed list of everything that left a document in a readable form (an export, a print, a PDF): who, when, what and which parts. It is not part of the history, and nothing removes an entry from it.
_avoid_: audit log, export log, history

**Original**
The file an imported document was made from, kept sealed inside the document if the person chose to keep it.
_avoid_: source file, attachment

**Private notes**
A person's own notes in a document, kept in her scrapbook. Nobody else can read them, not an owner and not the recovery key; sharing one makes an independent copy, and they are deleted when she leaves the document or is removed from it.
_avoid_: private domain, private part

### History

**Command**
One change to a document's content, of a named kind, that can be undone.
_avoid_: edit, change, operation, action

**History**
All the steps of a document, on all its branches; also called the document history. The chat sits beside it and is not part of it.
_avoid_: log, command log, timeline, versions

**Step**
One command as it happened in a document: which command, which author, when, and on which branch. An undo or a redo is a step too.
_avoid_: entry, record, change, revision

**Branch**
One path through a document's history. Main is the main branch; a restore starts a new branch, and the branch left behind stays and can be switched back to.
_avoid_: line, fork, version

**Restore**
Going back to the document as it was after a step, usually a checkpoint, for everybody at once; the document continues on a new branch and nothing is lost.
_avoid_: revert, roll back, undo

**Redaction**
The permanent removal, by an owner, of what past steps or chat messages contained, leaving behind that they happened.
_avoid_: delete, erase, censor, remove

**Checkpoint**
A named point in a document's history that a person set on purpose and can go back to.
_avoid_: save, version, snapshot

**Chat**
The messages the users of a document write to each other, to everybody or to one user, each placed at the step when it was written.
_avoid_: comments, conversation, messages

### Things

**Thing**
Anything in a document that has a name, unique in that document, by which a user can reference it with # in the chat.
_avoid_: entity, element, item

**Object**
A text box, shape, image, chart, container or table placed in a page, a slide or a sheet; every object is a thing.
_avoid_: element, figure, shape (for objects of other kinds)

**Chart**
A picture drawn from a document's data, shown as an object, as a chart tab of its own, or both.
_avoid_: diagram, graph, plot

**Chart tab**
A tab of a computes document that shows one chart on its own, beside the sheets; a thing, but neither an object nor a sheet.
_avoid_: chart sheet, diagram tab

**Table**
A named grid of cells whose first row names its columns: a named range in computes, an object in composes and creates.
_avoid_: grid, list

**Named range**
A named rectangle of cells in a computes document, from a single cell up, either kept by hand or filled by a formula's result.
_avoid_: name (in this sense), defined name, range name

**Style**
A named look, defined by its purpose, put into slots; every slot with the same style serves the same purpose.
_avoid_: format, formatting, theme, look

**Facet**
One of four sides of a look, naming what can be set for it: text (how characters look), paragraph (how a stretch of text is laid out), box (the background, border and padding around content) and outline (a shape's paint). The values are always a style's own.
_avoid_: property group, aspect, CSS

**Style kind**
Which facets a style may hold, and so which slots it fits: a paragraph style (text, paragraph and box), a box style or an outline style. A style and the style it is based on are always of the same kind.
_avoid_: style type, category

**Palette**
The colours of a document, each named by what it means, shared by all its styles.
_avoid_: colour scheme, theme

**Palette colour**
One colour of a palette, named by what it means (accent, muted); every style that uses it follows when it changes.
_avoid_: colour role, swatch, theme colour

**Number format**
How the value of a cell reads (a percentage, an amount in euros, a date, a number of decimals), chosen for the cell itself, apart from its style, and never changing the value.
_avoid_: format (on its own), cell format, number style

**Container**
An object whose content is supplied and drawn by software outside claudia, such as LaTeX or Mermaid; its drawing is kept in the document, so that anyone can open it without that software.
_avoid_: rendered, rendered picture, embed, plug-in

**Slot**
A part of a document that always holds exactly one style: a paragraph, the words of a cell, the box of a text box. A thing may have several slots, each with its own purpose; some things have no slot, and many slots belong to no thing. A slot takes any style whose kind fits it.
_avoid_: element, styled item, container

**Purpose**
What something in a document is for: a style states it in words, and a column of a table takes one of the purposes of a computation (input, data, calculation, result).
_avoid_: role, function, intent

**Cell**
One box of a sheet or a table holding one value, with a style and a number format of its own; never a thing by itself, but a named range may be a single cell.
_avoid_: field, box

**Paragraph**
A stretch of text that takes one style.
_avoid_: block, line

**Heading**
A paragraph whose style gives it a level in the outline of the document; the title is the top level.
_avoid_: title (except for the top level), caption, header

**Run**
A stretch of a paragraph written by one author, whatever its style.
_avoid_: span; and never "run" for a stretch of one formatting, as Word uses it

**List**
A numbered or bulleted sequence of paragraphs that counts across the document; a list is a thing.
_avoid_: bullets, enumeration, numbering

**Item**
A paragraph that belongs to a list, at one of its levels.
_avoid_: bullet, point, entry

**Marker**
The bullet, dash, number or letter in front of an item, coming from its list, never typed.
_avoid_: bullet (for markers in general), numbering, label

**Marker scheme**
How a list's markers look, level by level.
_avoid_: numbering scheme, numbering, list style, bullet style

**Reference**
Words in a document's text or chat that point at a thing and always show it as it is now: in the text by its number, words, page or name, in the chat (written with #) by its name.
_avoid_: link, field, cross-reference, tag

**Mention**
The @ in a chat message that addresses it to one user.
_avoid_: ping, address

### The ai at work

**AI mode**
How one person wants the ai to treat her requests in one document: act (it makes the change) or propose (it offers the change).
_avoid_: autopilot, review mode, permission, suggest

**Proposal**
Changes to a document that are offered but not made, until a person accepts or rejects them; seen by everybody or only by the one who asked.
_avoid_: suggestion, tracked change

**Remark**
A note the ai leaves at a place in a document that offers no change; a person dismisses it.
_avoid_: comment, annotation

**What-if**
A private copy of a document in which one person tries changes before carrying them out as one step.
_avoid_: sandbox, scratch copy, preview, branch
