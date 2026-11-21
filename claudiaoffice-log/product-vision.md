
We develop an open-source office suite called claudia.

# Who is it for?

Claudia wants to make Linux on desktop computers more attractive to end users. 
It would be really cool if e.g. a school, a science lab or a county administration decided to introduce claudia.

Initially however anyone working with classical office software like MS Office would be a potential user. 
Claudia should offer maximum compatibility with MS Office and OpenDocument standards wherever possible given
its feature set. It contains composes (Word), creates (Powerpoint) and computes (Excel).

The really new ideas and features that claudia will integrate however are geared towards

Education
Scientists 
Writers of stories, or books of all kinds
Intellectuals 
People tackling complex problems from multiple angles

Anyone who wants to turn an idea into a polished representation of it - and then work to make it real.

# What is it like to use it?

Claudia helps single users or groups of users to do deep work, think critically and reason properly. It optionally 
supports reflection on the user's work process and a light goal tracking. It supports coherence. With it, users can 
turn a thought into something others can easily understand, and keeps her thinking critically on the way. 

Computes, composes and creates are three forms of one story: a model that simulates something, a text that explains the background and what was found, a presentation that tells the arc from inspiration to insight. Users are not pushed into one way of working, but moving between the forms must be truly easy, and the evidence must travel with the story.

It should be inspired by the thinking of Bret Victor: it helps users with co-thinking, and user understanding through interaction and visualization/simulation of and with the data. It provides immediate feedback to user action whenever possible.
It allows direct manipulation and explorable explanations. It allows for thinking in alternatives and tracking states
of ideas, documents and data over time.

# What are unique selling points?

## AI support that 'plays by the rules'

The suite has support by agentic ai. The user can run her own model like qwen or deepseek using openvino integration, or
add a connection to claude.ai. 

Each of the programs of the suite integrates the AI the same way via a the "dock" in workspace containing the document history (all commands that were used to create the current document state) and a chat function, with which users can mention each other using @<username> <message>. The AI is just another user - there can be only one ai user per document and session.

## Privacy and encryption

A document has one owner, potentially several editors and viewers. The server has administrators. Documents are encrypted by default with a password that is specific to the document for the participating user. The owner can invite other users to 
become editors or viewers. There is one recovery key created when the document is created. There is no central user database,
user names are specific to a document. Documents are anonymous boxes that have a owner-provided name, a unique id on the server, an optional list of tags and a description. 

## Extensibility

Claudia makes it simple for power users to be extended. Features around this are user-defined functions in Python in computes,
or the option to use containers: a box that shows a rendering of a text command. Containers include Latex formulas, mermaid
diagrams or typst commands, and that list may grow.

## Separation of style and content

Like Latex, claudia separates styling from content. This avoids formatting mess for end users. By default the simple way
is to apply a style to something, not to set the many individual attributes a style may have for a given entity. Claudia
encourages styles to have meaning and purpose in communicating the content of the document.

One core principle of claudia is that _every thing (entity) in a document has a referenceable name_ and an optional description.
This allows users and the AI to refer to specific things in the chat by tagging them with #. Referenceable things include but are not limited to named cell ranges (computes), tables, headings and paragraphs (composes), textboxes (all apps), images (all apps)
and rendered containers (all appps).

## Stories across the suite

The suite supports linking thoughts, entities, ideas, content across its three components. For this to work, things in documents need a name.

A natural scientist or an accountant works something out in computes; the suite helps turn that into a summary write-up, or a plan for explaining the steps of thought. Someone writes a document in composes and wants to tell others; the suite helps turn the thoughts into a presentation in creates.

## Work process help

Documents may go through phases. In composes: **draft** (a backlog list, notes), **writing**, **polishing**. Creates gets the same kind of help (who is the presentation for, what does it need to achieve, how to structure it, how to build it). The phases serve the "think" part of the suite and suit scientific users, public administration and schools. Nobody is required to use them.

Goal, audience and phase are only suggestions and at most document metadata. A user does not have to follow phases or always have a goal. The user is offered one option, _"What would you like to achieve with this document?"_, and goal, process and phases are derived from the answer. 

Another way of helping the users is a deep work mode or focus mode.

The next feature is the binder: a place for notes, links, images, scribbles, anything that the user may wishes to refer to
or have access to while working on her documents. The binder is private to the user even though it is part of the document
at hand. Items from the binder can be shared with other editors or the owner.

Another feature is the corkboard view: it allows users to see connections within their document from a birds eye view through 
a representation of document content in connected 'sticky notes'. 
It allows users in computes to see connections between named ranges (becoming represented as sticky notes) through formulas;
in composes every section or chapter can have a summary (its name is the title itself) that goes on the sticky note, in creates every slide is a sticky note.

# Three apps: computes, composes, creates

## computes

This is an Excel stand-in. Its formula language should be max compatible with Excel.

It focusses on the following broad use cases:
- Science
- Data analysis and visualisation
- Education and simulation, interactive data representation
- Project Management
- Financial Modeling


## claudia composes

- A **Word stand-in** for polished documents: reports, letters, scientific and technical texts with formulas, meeting notes, drafting together. The tools and the AI help take a draft or a list of bullet points towards a polished version.
- **Flow is the default view.** The page view is a switch in the main editing window.
- **Styles first.** You mark something as a heading. Every marking or style difference serves a purpose the user can name. When a style is applied that has no name yet, the user is invited to name it, with a small hint that the name should say what it is for.
- **Suggestions and authorship.** Edits by the AI are suggestions to review. People's contributions in live work are immediate. Each contribution should be identifiable by author.
- **Thinking aids from the AI.** Spelling, word choice, complicated wording, language style; later structure, and whether the plot or flow is understandable. Summaries and content proposals on request. An outline view that can be rearranged and side-by-side versions of a paragraph also appeal.

## claudia creates

- **Templates and style definition come first**, as in LaTeX's separation of content and layout. Inspiration: Beamer. Few shapes, not a drawing program.
- **Better than PowerPoint's masters.** Slides come from a template. In PowerPoint one is often unsure where the slide in front of you was derived from, and is tempted to edit the page number or format the title on each slide separately. Claudia must avoid that.
- **Connected thoughts.** Prezi's idea of connectivity: a thought, or a link in a chain of thoughts, becomes a slide.
- **Storytelling and audience.** Who and what is the presentation for, how should it be structured to reach that audience, and how should the work itself be organised to reach the goal?
- **Thinking aids from the AI.** Cluttered slides, poor word choice, spelling, structure; design choices such as colour schemes from the stated purpose and goal, and fonts from the purpose.
- **Collaboration.** Track changes records objects added and removed and text edited in them. Marking a shape or text box (or a group) locks it for others.
- **Media and formats.** JPEG, SVG, GIF and other figure and image formats. Import and export of PPTX and the OpenDocument presentation format.
- **LaTeX formulas and Mermaid diagrams** in creates, as in the other two apps.


