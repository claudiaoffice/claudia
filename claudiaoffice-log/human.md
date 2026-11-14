
Work plan for Nov 14/15th 2026

- [x] integrate all existing work
	- [x] QA
	- [x] real world docs
	- [x] text rendering containers groundwork
	- [x] bitv, if necessary
- [ ] clean up branches, delete remote ones too
- [ ] focus topics
	- [ ] file management => to do this, introduce the one-server approach
		- [ ] use worker pool for real!
	- [ ] UI for import of MS OFfice and ODF files, otherwise makes no sense to have real world docs
	- [ ] QA + security
		- [ ] performance
		- [ ] scaleway: replace not new image
		- [ ] deployability server
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
	- [ ] printing in computes
	- [ ] finish text rendering containers
		- [ ] typst
		- [ ] mermaid
		- [ ] latex
			- [ ] first usecase: formulas in composes
	- [ ] bibliography with bibtex support and zotero


explore QNAP docker server