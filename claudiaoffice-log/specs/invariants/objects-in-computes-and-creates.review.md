# Questions on the computes and creates invariants (drafts, bug eater batch 4)

`objects-in-computes.feature` and `objects-in-creates.feature` are drafts (`@draft`): nothing runs them until the
owner approves them. They follow `objects-in-composes.feature` scenario by scenario, with what differs in each app.
Each question has a proposed default; cross it out or change it.

1. **Which kinds in the pilot?** Shapes, Textbox, Image and Containers across all three apps. 

2. **Where an object is, in computes.** The draft says "at B5" (its top left cell). To have a test for whether an object keeps its pixels when rows change size (UX-53, open),  insert rows above it.

3. **Typing around it.** Composes types before and after the object; computes types into the cells next to it; creates goes to another slide and back and inserts a textbox above the object and types into the textbox

4. **The kept-file scenario** (computes only, "added to an opened file is in that file when saved again") checks CODE-66
   and CODE-70 from the person's side. Creates has no such case yet: a creates patch refuses an added object
   (`UnsupportedEdit`) and writes the file anew. 
   
   Owner: Since this is a usability bug, the scenario should check for kept-file in all three apps. The goal is to save an imported file from another office format in every claudia file type and to use that kept file on export again to have fewer losses.
 
4. **Names in files.** Both drafts check that an object's name comes back from a file (D550; for creates CODE-25,
   batch 4). Whether a chart's name comes back from xlsx and ods has not been checked yet: the scenario will say so
   when it is bound. *Default:* as drafted.
   
5. **Browsers.** The same scenarios as composes get `@firefox`. *Default:* as drafted.
