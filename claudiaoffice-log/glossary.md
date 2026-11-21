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
The user who made a step.
_avoid_: writer, creator

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
A text box, shape, image, diagram, rendered picture or table placed in a page, a slide or a sheet; every object is a thing.
_avoid_: element, figure, container, shape (for objects of other kinds)
