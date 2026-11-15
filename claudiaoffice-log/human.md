
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
		- [ ] deployability server, to QNAP and elsewhere
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


explore QNAP docker server