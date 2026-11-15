
Work plan for Nov 14/15th 2026

- [x] integrate all existing work
	- [x] QA
	- [x] real world docs
	- [x] text rendering containers groundwork
	- [x] bitv, if necessary
- [x] clean up branches, delete remote ones too
- [ ] focus topics
	- [x] file management => to do this, introduce the one-server approach
		- [ ] use worker pool for real!
		- [x] progress bar when importing
		- [x] size of import dialog may be too small => needs to adapt to filename
		- [x] in desktop apps: while on frontpage, show only relevant menu items (open file), not stuff that is not possible (Edit > Insert)
		- [x] in web app front page: move usable area up on the screen, otherwise we waste screen space
		- [x] hide/unhide in password field, also in "share" dialog
		- [ ] in the menu of computes > tools e.g. "resample" only makes sense if there is any
		      "RANDOM" command anywhere, same goes for the "draw 0" count at the right most edge above the history&chat dock. Could we make it a principle that stuff that is not meaningful in the respective context is invisible? So the tools menu would expand with new entries IF there is a random function somewhere.
		- [x] the app icon is gone for the linux client when starting from shell - normal?
		- [ ] in the linux client "open file", "new" on in the native menu doesn't have any effect
		- [ ] in the mac client "open a file" on the front page doesn't do anything, neither does any of the native menu File entries
			- [ ] fix the crash at the end ("closed unexpectedly")
		- [ ] rotation UI in all three apps
		- [ ] macos client still picks random port and the button "open document" as well as native menu entries dont do anything.
		- [ ] print on desktop clients "has no fonts"
		- [ ] export to office format in desktop client => where do the files go? In web app theyre downloaded in the browser, perfect!
		- [ ] win client 
			- [ ] still has npm message "npm warn deprecated glob@10.5.0: Old versions of glob are not supported, and contain widely publicized security vulnerabilities, which have been fixed in the cu"
			- [ ] opens object inspector on startup?
			- [ ] still shows non-useful menu entries at front page and seems to connect to random server port => state of the client?
			- [ ] invalid menu entries like "review this text" still exist
		- [ ] cant find fonts in a desktop client when printing
		- [ ] in help system the Markdown isn't rendered but raw ("how do I..." sections)
		- [ ] can't move the search&replace overlay in computes
	- [x] UI for import of MS OFfice and ODF files, otherwise makes no sense to have real world docs
	- [ ] QA + security
		- [ ] versioning announcement of server on start page
		- [ ] performance
		- [ ] scaleway: replace not new image
		- [ ] **import-export-wiring** every internal feature should be connected to the Importer/Exporter
			- [ ] e.g. ordered/unordered lists in composes not imported/exported
		- [ ] **ongoing on branch "search"** extend regex search from computes to creates and composes
		- [x] deployability server, to QNAP and elsewhere
		- [ ] CI on github, get it green!!
		- [ ] desktop client tests (visual deviations)
		- [ ] decision log should reflect the reality (e.g. "Linux client is GTK completely" => wrong!)
	- [ ] every object should have a name (even if its not in the UI yet); and objects can have relationships between each other (reference each other)
		- [ ] images
		- [ ] textboxes
		- [ ] shapes
		- [ ] paragraphs
		- [ ] lists in composes
		- [ ] styles
		- [ ] anything else we have as entities?
	- [ ] **computes-print** printing in computes
	- [ ] finish text rendering containers
		- [ ] typst
		- [ ] mermaid
		- [ ] latex
			- [ ] first usecase: formulas in composes & creates
		- [ ] excalidraw
	- [ ] bibliography with bibtex support and zotero
	- [ ] tables in composes
	- [ ] cell formats beyond style in Excel (%, €)

* LAMBDA in Excel
* dynamic arrays in Excel
* computation with # symbol as in GEMO excel
* 


- [x] explore QNAP docker server


Linux: still random port
File > Open doesn't give feedback
File > New marks the "create new" on front page => good!
File > Open a file allows import => good!
![[Pasted image 20261115105251.png]]Missing font problem gone
Download PDF in print view => perfect
Export now opens file location picker => perfect
Dragging an external file into the window when the start page is visible => does not import, is that possible?


windows client:
fresh checkout of main
npm run build
then main window doesnt show anything

macos:
"open a file" on start page opens file picker
"this computer" still shows "random" port
File > Open highlights the search bar => good!
File > Open a file opens file picker => perfect!
File > New puts cursor in "document name" input and highlights the "new" seciton => perfect!
printing works / fonts instlalled => perfect
dragging file from finder into start page window starts impot => perfect!
on the next opening of the application I did not see the start page => same as with windows. maybe two servers?


![[Pasted image 20261115113530.png]]

"in x texts" that is confusing in composes, because average user thinks of his doc as one text, just "n matches" is good.

"look in" and the buttons below look all very nice but should be smaller, or a multi-select (checkboxed) dropdown, because they take too much screen space, and "replace with" and "build pattern" are small links only, and the distance to "n matches" is too small.

If you click on the three dots in the dialog and select "About searching and patterns" the help panel opens below the dialog, but there is no help topic linked to "about searching and patterns", and the fact that the help opened isn't visible, because the dialog box is hovering above it.

You should be able to move the dialog around on the screen, but at the moment its fixed.