Feature: Tables in a composes text (E9.32)
  As a writer, I want to put a table in my text, fill it, and change its shape, so that I do not have to leave my
  text for a small table. What every object must do (be there once, reload, undo, colleagues, files) is in
  `specs/invariants/objects-in-composes.feature` and is not repeated here. `Q<n>` points to a question in
  `tables.review.md`; a scenario tagged `@needs-decision` says what I propose and waits for the answer, and one tagged
  `@after:object-interaction` is decided (D1221-D1226) but lives on a branch that is not merged yet. Selecting, moving,
  scaling and the object menu as such are the contract of D1221 and its own E2E (`web/e2e/objects.cjs`, planned);
  they are not repeated here, only what is particular to a table.

  Background:
    Given a new composes document "report" in which I am Ann, an owner
    And the text has the paragraphs "Before" and "After"
    And my caret is at the end of "Before"

  # ================================================================ inserting

  @core @firefox
  Rule: Insert ▸ Table… puts a table of the size I ask for after the paragraph I am in

    Scenario: The dialog is opened from the menu and from the keyboard
      When I choose Insert ▸ Table…
      Then a dialog asks for the number of columns and rows and whether the first row is the header
      When I close it with Esc
      And I press Ctrl+Shift+F
      Then the same dialog is open, with the focus in the first field

    Scenario: A table of 3 columns and 4 rows with a header
      # Q1: 4 rows including or excluding the header?
      When I insert a table of 3 columns and 4 rows with a header
      Then the table is between "Before" and "After"
      And the table has 3 columns
      And the table has a header row, in the header look, and 3 body rows
      And all boxes are empty
      And I can see where every box is, also while it is empty, and all 12 boxes are inside the text area
      # Q2
      And the caret is in the first box of the header row
      And the table has a name such as "Table 1"

    Scenario: A table without a header
      When I insert a table of 2 columns and 2 rows without a header
      Then the table has no header row and 2 body rows
      And the columns are called "Column 1" and "Column 2"

  @extended
  Rule: The dialog keeps me inside the limits (100 rows, 10 columns)

    Scenario Outline: Sizes outside the limits cannot be inserted
      When I choose Insert ▸ Table…
      And I ask for <columns> columns and <rows> rows
      Then "Insert" is not available
      And the dialog says what the limits are

      Examples:
        | columns | rows |
        | 0       | 3    |
        | 11      | 3    |
        | 3       | 0    |
        | 3       | 101  |

    Scenario: The largest allowed table can be inserted
      When I insert a table of 10 columns and 100 rows with a header
      Then the table has 10 columns and 100 rows
      # Q3: what is "fast enough"?
      And the page shows it without freezing for more than a second

  @extended @needs-decision
  Rule: Where a table goes when the caret is not at the end of a paragraph (Q4)

    Scenario: The caret is in the middle of a paragraph
      Given my caret is between "Bef" and "ore"
      When I insert a table of 2 columns and 2 rows
      Then the paragraph "Before" is still in one piece
      And the table is right after it

    Scenario: The caret is in an empty paragraph
      Given the text has an empty paragraph after "Before"
      And my caret is in the empty paragraph
      When I insert a table of 2 columns and 2 rows
      # Q5
      Then the table is where the empty paragraph was, and no empty paragraph is left behind

    Scenario: The caret is already in a table
      Given I have inserted a table of 2 columns and 2 rows
      When I choose Insert ▸ Table…
      # Q6
      Then the entry is not available, or the table goes after this table, not into a box

  @extended @two-users
  Rule: A reader cannot insert a table

    Scenario: The entry is not available to a reader
      Given Cleo, a reader, has the document open
      Then for Cleo, Insert ▸ Table… is not available

  # ================================================================ typing in boxes

  @core @firefox
  Rule: I fill a table with the keyboard, as in a spreadsheet

    Background:
      Given I have inserted a table of 3 columns and 3 rows with a header
      And I have typed the header "Bed", "Crop", "Kilos"

    Scenario: Tab goes to the next box, and at the end of a row to the first box of the next
      When I type "Roof 1" in the first body box and press Tab
      And I type "Kale" and press Tab
      And I type "12" and press Tab
      Then the caret is in the first box of the second body row
      And the first body row reads exactly "Roof 1", "Kale", "12", each once
      And the history shows one entry for each of the three boxes

    Scenario: Shift+Tab goes back
      Given the caret is in the first box of the second body row
      When I press Shift+Tab
      Then the caret is in the last box of the first body row

    Scenario: Tab in the very last box adds a row and puts the caret in it
      Given the caret is in the last box of the last row
      When I press Tab
      Then the table has one more body row, at the end
      And the caret is in the first box of that row

    Scenario: Enter takes what I typed and goes one box down
      When I type "Roof 1" in the first body box and press Enter
      Then the first body box reads exactly "Roof 1", once
      And the history shows one entry for it
      And the caret is in the first box of the second body row
      And the box did not get a second line

    Scenario: The arrow keys move between boxes, and left and right only at the edge of the words
      Given the first body box reads "Roof 1" and the caret is in the middle of it
      When I press the right arrow
      Then the caret moves inside the words and I am still in the same box
      When I press End and then the right arrow
      Then the caret is in the next box
      When I press the down arrow
      Then the caret is in the box below

    Scenario: What I type is kept when I click somewhere else
      When I type "Roof 1" in the first body box
      And I click into the paragraph "After"
      Then the first body box reads exactly "Roof 1", once
      And the history shows one entry for it

    # Q7: where does the caret go?
    Scenario: Esc gives back what was there and leaves the table
      Given the first body box reads "Roof 1"
      When I change it to "Roof 2" and press Esc
      Then the first body box reads "Roof 1"
      And the caret is in the text, next to the table

    Scenario: Undo takes back one box, not one letter
      When I type "Roof 1" in the first body box and press Tab
      And I undo
      Then the first body box is empty

  @extended @needs-decision
  Rule: Words not committed yet when the page is left (Q8, the table's own part)

    Scenario: I reload the page while I am still in the box
      Given I have inserted a table of 2 columns and 2 rows
      And I have typed "Roof 1" in the first body box without leaving it
      When I reload the page and open "report" again
      # proposal: kept, by committing when the page is hidden; today it would be lost
      Then the first body box reads "Roof 1"

  @extended
  Rule: A lost connection is the one concept of the whole app: a banner, and nothing is saved meanwhile (Q8)

    Scenario: What I type while the banner is shown is not saved, as the banner says
      Given I have inserted a table of 2 columns and 2 rows
      And the first body box reads "Roof 1"
      When the connection to the server is lost
      Then I see the banner "The connection was lost. Trying to get back… what you do now is not saved."
      When I type "Kale" in the second body box and press Tab
      And the connection comes back
      Then the banner is gone
      And the table is as the server had it: "Roof 1" in the first body box, and the second body box is empty

  @extended
  Rule: Words in a box behave

    Background:
      Given I have inserted a table of 2 columns and 2 rows with a header

    Scenario: A long text wraps inside its box and the table stays inside the page
      When I type a sentence of 300 characters in the first body box
      Then the row grows taller
      And the table is not wider than the text

    Scenario: One very long word does not push the table out of the page
      When I type 80 letters without a space in the first body box
      Then the table is not wider than the text

    # Q9
    Scenario: Text with several lines is pasted into a box
      When I paste "one\ntwo\nthree" into the first body box
      Then the box keeps one line, and the lines go into the boxes below, adding rows if needed

    Scenario: Letters from other languages
      When I type "Grünkohl – 12,5 kg ✓ 日本語" in the first body box
      Then the first body box reads "Grünkohl – 12,5 kg ✓ 日本語" after a reload

  # ================================================================ changing the shape

  @core @after:object-interaction
  Rule: The table menu is the right-hand click, and holds what the Edit menu no longer has (D1224, D1225)

    Scenario: A right press in a box selects the table and opens its menu
      Given I have inserted a table of 2 columns and 2 rows
      When I press the right mouse button in a box
      Then the table is selected
      And a menu opens that holds, in this order: Name & describe…, Table options…, Merge cells, Split cell, Sort ▸, Delete table
      And it does not hold Rotate by…
      And neither the paragraph menu nor the browser's menu opens

    Scenario: The Edit menu does not carry them any more
      Given my caret is in a box
      Then the Edit menu has none of Table options…, Merge cells, Split cell and Sort

    Scenario: The editing aids are shown while I edit and are not printed
      Given I have inserted a table of 2 columns and 2 rows in the look "Plain"
      Then a faint frame and the lines between the boxes are shown in the editor
      When I open the print preview
      Then the preview shows the look "Plain" only, without the faint frame and lines

  # N2: D1224 leaves "Insert/delete" to the row and column headers, and composes' tables have no header UI yet; the
  # words below say what a person does, not where she does it. Tab in the last box (above) adds a row either way.
  @core @needs-decision
  Rule: I add and take away rows and columns

    Background:
      Given I have inserted a table of 3 columns and 3 rows with a header
      And the body is filled with "Roof 1", "Kale", "12" / "Roof 2", "Beans", "7" / "Yard", "Leek", "30"

    Scenario: A row above and below the caret's row
      Given my caret is in the box "Beans"
      When I add a row above
      And I add a row below
      Then the body reads, from the top: "Roof 1", an empty row, "Roof 2", an empty row, "Yard"
      And my caret is still in the box "Beans"

    Scenario: A column to the right of the caret's column
      Given my caret is in the box "Kale"
      When I add a column to the right
      Then the table has 4 columns, the new one after "Crop", with an empty header and empty boxes

    Scenario: Deleting a row and a column
      Given my caret is in the box "Beans"
      When I delete the row
      And I delete the column
      Then the table has 2 columns and 2 body rows, and "Roof 1" and "Yard" are still where they were, in their rows

    Scenario: Each of these is one undo
      Given my caret is in the box "Beans"
      When I delete the row and undo
      Then the row is back with "Roof 2", "Beans", "7"

    Scenario Outline: The keys do the same as the menu
      Given my caret is in the box "Beans"
      When I press <keys>
      Then <result>

      Examples:
        | keys             | result                          |
        | Shift+Alt+Down   | a row is added below            |
        | Shift+Alt+Up     | a row is added above            |
        | Shift+Alt+Right  | a column is added to the right  |
        | Shift+Alt+Left   | a column is added to the left   |
        | Ctrl+Alt+-       | the row is deleted              |
        # as in computes, D1208
        | Ctrl+Alt+_       | the column is deleted           |

  @extended @needs-decision
  Rule: The edges of what can be deleted and added (Q10, Q11, N1)

    Scenario: The 101st row is refused, with a reason
      Given I have inserted a table of 2 columns and 100 rows
      When I press Tab in the last box
      Then no row is added
      And I am told that a table has at most 100 rows

    Scenario: The 11th column is refused, with a reason
      Given I have inserted a table of 10 columns and 2 rows
      When I add a column
      Then no column is added
      And I am told that a table has at most 10 columns

    # Q10 (answered 2026-11-19): deleting the last row or the only column removes the table. This replaces the
    # sentence of D1213 that says those entries are off. N1: with a header, the last *body* row is meant (a table needs
    # a body), so Q11 and Q10 do not collide.
    Scenario: Deleting the only body row removes the table
      Given I have inserted a table of 2 columns and 2 rows with a header
      When I delete the only body row
      Then the table is gone and the text around it is as it was
      And the history shows one entry, "Removed a table"
      When I undo
      Then the table is back as it was

    Scenario: Deleting the only column removes the table
      Given I have inserted a table of 1 column and 3 rows
      When I delete the column
      Then the table is gone and the text around it is as it was
      And the history shows one entry, "Removed a table"

    Scenario: The header row is not deleted like a body row
      Given my caret is in a header box
      When I delete the row
      # Q11
      Then I am told to use Table Options… to change the header rows

  @core @firefox
  Rule: Sorting by a column

    Background:
      Given I have inserted a table of 2 columns and 4 rows with a header
      And the header is "Crop", "Kilos"
      And the body is "Kale", "12" / "Beans", "7" / "Leek", "30" / "Apple", "100"

    Scenario: Ascending, numbers by value, header stays on top
      Given my caret is in a box of the column "Kilos"
      When I sort ascending
      # 7, 12, 30, 100, not "100, 12, 30, 7"
      Then the body reads "Beans", "Kale", "Leek", "Apple" in that order
      And the header is still the first row

    Scenario: Descending
      Given my caret is in a box of the column "Crop"
      When I sort descending
      Then the body reads "Leek", "Kale", "Beans", "Apple" in that order

    Scenario: Sorting is one undo
      Given my caret is in a box of the column "Crop"
      When I sort ascending and undo
      Then the body is as it was before

  @extended
  Rule: Sorting reads numbers the way the document's language writes them

    Scenario: German decimal commas
      Given the language of the document is German
      And the table has the body "a", "1,5" / "b", "10,25" / "c", "2"
      When I sort the second column ascending
      Then the order is "a", "c", "b"

    Scenario: Boxes that are not numbers go last and are not an error
      Given a column of numbers with one box reading "n/a"
      When I sort it ascending
      Then "n/a" is the last row and nothing is lost

  @extended @needs-decision
  Rule: Merging and splitting boxes (D1205; Q12)

    Scenario: Two neighbouring boxes become one
      Given my caret is in the box "Kale"
      When I choose Edit ▸ Merge Cells
      Then "Kale" and the box to its right are one box, and the words of both are in it

    Scenario: Splitting gives the words back to the first box and leaves the others empty
      Given "Kale" and its neighbour are merged
      When I choose Edit ▸ Split Cell
      Then there are two boxes again

    Scenario: Adding and deleting rows around a merged box does not tear it
      Given a box spans two rows
      When I delete one of those rows
      Then the box is one row high and nothing else moves

  # ================================================================ options, totals, looks

  @core
  Rule: Table Options… changes how the table looks, not what it says

    Background:
      Given I have inserted a table of 3 columns and 4 rows with a header
      And my caret is in the table

    Scenario: The dialog opens from the menu, from Ctrl+Shift+L and from the chip, and closes with Esc
      When I open Table Options… by each of the three ways
      Then I see the same dialog each time
      And Esc closes it and the caret is back where it was

    Scenario Outline: The looks
      When I choose the look "<look>"
      Then the table is drawn in the look "<look>", once, and the words are unchanged
      When I reload the page and open "report" again
      Then it is still in the look "<look>"

      Examples:
        | look  |
        | Rules |
        | Grid  |
        | Plain |

    Scenario: Banded rows, header rows and width
      When I turn on banded rows
      And I set the number of header rows to 2
      And I set the width to 60 percent
      Then every second body row is banded
      And the first two rows are the header
      And the table is 60 percent as wide as the text

    Scenario: A column can be a number column
      When I set the column "Kilos" to numbers
      Then its boxes are aligned to the right

  @core @firefox
  Rule: A column can have a total, which is not typed but worked out

    Background:
      Given I have inserted a table of 2 columns and 4 rows with a header
      And the header is "Crop", "Kilos"
      And the body is "Kale", "12" / "Beans", "7" / "Leek", "30"

    Scenario: A sum
      When I set the total of "Kilos" to sum
      Then there is a last row in the total look, reading "49" under "Kilos"
      And that row has no box I can type in

    Scenario: The total follows the numbers
      Given the total of "Kilos" is a sum
      When I change "7" to "10"
      Then the total reads "52"

    Scenario Outline: The other totals
      When I set the total of "Kilos" to <kind>
      Then the total reads "<value>"

      Examples:
        | kind  | value |
        | mean  | 16.33 |
        | count | 3     |
        | min   | 7     |
        | max   | 30    |

    Scenario: A box that is not a number is skipped, and the total says so
      Given the "Kilos" box of "Leek" reads "n/a"
      When I set the total of "Kilos" to sum
      Then the total reads "19"
      And the total says that one box was skipped

    Scenario: Taking the total away
      Given the total of "Kilos" is a sum
      When I set the total of "Kilos" to none
      Then the total row is gone and the boxes are as they were

  @extended @after:object-interaction
  Rule: Taking a table away (Q13: not asked first, one entry in the history, one undo)

    Scenario Outline: The ways to take a table away
      Given I have inserted a table of 2 columns and 2 rows and worked in it
      When I <way>
      Then the table is gone and the text around it is as it was
      And I was not asked anything first
      And the history shows one entry, "Removed a table"
      When I undo
      Then the table is back with what I had written

      Examples:
        | way                                        |
        | choose Delete table in the table menu      |
        | select the table and press Del             |

  # ================================================================ name, description, references

  @extended
  Rule: A table can be named, described and referred to

    Scenario: Renaming
      Given I have inserted a table of 2 columns and 2 rows
      When I rename it to "Harvest"
      Then "Harvest" is its name in the "#" list of the chat
      And a second thing cannot be given the name "Harvest"

    Scenario: A reference in the chat takes everybody to the table
      Given Ben has the document open and the table is called "Harvest"
      When I write "#Harvest" in the chat, choosing it from the list
      And Ben clicks that tag
      Then Ben's view shows the table

    Scenario: The names of the columns are the words of the header
      Given the header is "Crop", "Kilos"
      Then the columns are called "Crop" and "Kilos" in Table Options…
      When I change the header box "Kilos" to "Weight"
      Then the column is called "Weight" in Table Options…

  # ================================================================ among the paragraphs

  @core
  Rule: A table sits between paragraphs and goes with the text it belongs to

    Background:
      Given I have inserted a table of 2 columns and 2 rows
      And I have typed "Roof 1" in the first body box

    Scenario: Adding paragraphs above moves the table down, once
      When I add a paragraph "New" before "Before"
      Then the order is "New", "Before", the table, "After"
      And the table is shown once

    # Q14
    Scenario: Splitting the paragraph it hangs from takes the table along
      When I press Enter in the middle of "Before"
      Then the table follows the paragraph it belonged to, and is shown once

    # Q14
    Scenario: Deleting the paragraph it hangs from
      When I delete the whole paragraph "Before"
      Then the table is still there, once, with "Roof 1" in it, and is not deleted by accident

    # Q15
    Scenario: Backspace at the start of the paragraph after the table
      When I press Backspace at the start of "After"
      Then the table is not deleted, and "After" is not joined into a box

    # Q15, changed: see the review file, B-list N4
    @needs-decision
    Scenario: Selecting text across the table and deleting it
      When I select from the middle of "Before" to the middle of "After" and delete
      # proposal changed to match Q13 and D1225 (Del removes an object without a question): no question, one undo
      Then the table is deleted with the text between, and I was not asked
      And one undo brings back the text and the table together

  @core @firefox
  Rule: A long table runs over the pages

    Scenario: Rows are never cut in the middle, and the header comes again
      Given I have inserted a table of 3 columns and 60 rows with a header
      When I open the page view
      Then the table is on more than one page
      And every page that has part of the table starts it with the header row
      And no row is split between two pages
      And every box is shown once in all the pages together

    Scenario: The print preview and the PDF show the same
      Given a table of 3 columns and 60 rows with a header, each box holding its own number
      When I open the print preview
      Then I see the same pages as in the page view
      When I print to PDF
      Then the PDF contains each number exactly once

  # ================================================================ colleagues

  @core @two-users @firefox
  Rule: Two people fill the same table

    Background:
      Given Ben, an editor, has the document open as well
      And I have inserted a table of 2 columns and 3 rows with a header

    Scenario: Each sees what the other commits
      When I type "Kale" in the first body box and press Tab
      Then Ben sees "Kale" in the first body box
      When Ben types "Leek" in the second body row's first box and presses Tab
      Then I see "Leek" there

    Scenario: A box somebody is in is locked for the other
      When I put my caret in the first body box
      Then Ben cannot type in that box, and he sees whose it is
      But Ben can type in every other box

    Scenario: Rows are not taken away from under somebody
      Given my caret is in the second body row
      When Ben tries to delete that row
      Then the row stays, and Ben is told that Ann is in it
      When my caret leaves the row
      And Ben deletes it
      Then the row is gone for both of us

    Scenario: Undo is my own
      Given I typed "Kale" in a box and Ben then typed "Leek" in another box
      When I undo
      Then "Kale" is gone and "Leek" is still there

  @extended @two-users
  Rule: A reader sees tables, and cannot change them

    Scenario: Boxes are read-only for a reader
      Given Cleo, a reader, has the document open
      And I have inserted a table and typed "Kale" in a box
      Then Cleo sees "Kale"
      And Cleo cannot type in the box, nor open the options to change them, nor remove the table

  # ================================================================ the assistant

  @extended @needs-decision
  Rule: The assistant (the stand-in, not a real model) and tables (Q16)

    Scenario: It fills in words when I ask, in "act" mode
      Given I have inserted a table of 2 columns and 3 rows with a header "Crop", "Kilos"
      When I write "@ai put Kale in the first row" in the chat in "act" mode
      Then the first "Crop" box reads "Kale"

    Scenario: In "suggest" mode I see a proposal first and nothing changes until I take it
      When I ask the same in "suggest" mode
      Then I am shown a preview, and the table is unchanged until I accept

    Scenario: It does not change the shape
      When I write "@ai add a column" in the chat
      Then no column is added and the assistant says it can only change the words

  # ================================================================ search

  @extended
  Rule: Search and replace finds words in boxes

    Scenario: Found, named, replaced
      Given a table "Harvest" with the box "Kale"
      When I search for "Kale"
      Then I am told it is in the table "Harvest"
      When I replace it with "Cavolo nero"
      Then the box reads "Cavolo nero" and it is one undo

  # ================================================================ a person who cannot use a mouse or a screen

  @core @firefox
  Rule: A table can be used with the keyboard and a screen reader (BITV)

    Scenario: A table is a table to assistive technology
      Given I have inserted a table of 3 columns and 3 rows with a header
      Then it is exposed as a table with a name, header cells for its columns, and rows and columns counted
      And every box has a name that says its row and its column, such as "Row 2, Crop"

    Scenario: I can get into the table, work through it and out of it with the keyboard alone
      Given I have inserted a table and my caret is in the text before it
      When I press the keys to enter the table
      And I fill the first row with Tab
      And I press Esc
      Then the caret is in the text, next to the table
      # Q7: how does the keyboard user get in?
      And I never needed the mouse

    Scenario: Dialogs of tables return the focus to where I was
      When I open and close Insert ▸ Table… and Table Options…
      Then the focus is back where it was each time

  # ================================================================ files

  @extended
  Rule: A table in a file (details of the format are checked in the package tests)

    Scenario Outline: Downloaded and opened again
      Given a table of 3 columns and 3 rows with a header, banded, in the look "Grid", with the body filled
      When I download the document as <format> and open that file as a new document
      Then the new document has one table with the same header, words, banding and a look I recognise

      Examples:
        | format       |
        | OpenDocument |
        | Word         |

    Scenario Outline: A table made in another program
      # Q17, chosen: the library's existing regular table in each format
      Given the file "<file>"
      When I open it
      Then its table is one table of ours, shown once, between its two paragraphs, and I can type in it

      Examples:
        | file                                                 |
        | test-documents/docx/beyond-claudia/table/source.docx |
        | test-documents/odt/beyond-claudia/table/source.odt   |

    Scenario: A table we do not understand is kept and listed, not lost
      # Q17, chosen: a new fixture "tables-irregular" in test-documents/_build_fixtures.py, to be built with the tests
      Given the file "test-documents/docx/tables-irregular/source.docx" with a table inside a table and a merge that is not a rectangle
      When I open it and download it again
      Then those tables are still in the downloaded file, and the import said they were not understood
