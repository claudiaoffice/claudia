# Review notes for `keys-and-people.feature` (slice C of E2 round two)

For the owner to read before the scenarios are agreed. Drafted 2026-11-19 with the code, not before it; change anything.

| Scenario | Runs in | What it protects |
|---|---|---|
| Ann sees everybody with a role each | Chrome, real server | D1263: the list is the owner's; owners have no select and no Remove |
| Ann lowers Ben to "only look" after being told | Chrome, two windows | the question names what is and is not protected; the dialog shows the new role; Ben's window says so and becomes a viewer's |
| Ann changes her mind | Chrome | nothing changes without the second click |
| Ann removes Ben, and Ben is out at once | Chrome, two windows | the question mentions private notes; Ben's window closes with a sentence and his password no longer opens the document |
| Ann carries on after the renewal | Chrome | the document is still there and writing still works under the new keys (the text she types survives a reopen) |
| An editor cannot open the Share dialog | Chrome | the entry is disabled for non-owners |
| The six `@extended` ones | unit tests | which parts a renewal touches; the interrupted renewal; letters and forged letters; private notes; who may change what on the wire |

Not run in a browser: a person who was away during the renewal and logs in later (unit tests of the letter), the recovery
key as a receiver of letters, a crash in the middle of a renewal, a very large document (the dialog's "about as long as
writing the file once" is argued, not measured).

The scenarios say `"plan"` for the document's name; the run uses a generated name and the step replaces it.
