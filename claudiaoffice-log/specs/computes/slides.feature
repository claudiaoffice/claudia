# Slides in computes
Feature: Slides in computes (E6.31)
  As someone who builds charts in a workbook, I want a slide among my sheets that holds a chart together with text
  boxes and shapes, so that a chart can have a page of its own with words beside it, and works like a slide in creates.
  A slide comes into existence only for a chart, and goes with its last object. The screens are
  `notes/mockups/computes-slides-*.svg`, the architecture `notes/e6-31-slides-in-computes.md`. The owner's answers
  to the review of 2026-11-22 are written into the scenarios (`Q<n>` names the question they answer); the decisions
  are D1470 to D1475.
  What every object does (selecting, moving, scaling, naming, the object menu as such) is in `specs/objects/` and is
  not repeated here.

  Background:
    Given a new computes document "sales" in which I am Ann, an owner
    And Sheet1 has "Region" and "Amount" in A1 and B1, and East 300, West 120 and North 70 below them

  # ================================================================ a chart as a slide

  @core @firefox
  Rule: Insert ▸ Chart… shows a chart as a slide of its own, right after the tab I am on

    # Step 3, owner 2026-11-23: the new slide gets the next free generic name "Slide n"; the name in the dialog is the
    # chart's, as with "Move to Slide" (Q1 of the review of 2026-11-22).

    Scenario: "A slide" is what the dialog offers first
      When I select A1:B4 and choose Insert ▸ Chart…
      Then the dialog offers to show the chart as "A slide" or as "A floating object on the sheet"
      And "A slide" is chosen
      And the name field asks for the name of the chart

    Scenario: The chart becomes a slide, right after the sheet I am on
      Given there is a second sheet "Costs"
      When I insert a bar chart "Sales" of A1:B4 as a slide
      Then the tabs read "Sheet1", "Slide 1", "Costs"
      And the tab "Slide 1" is marked as a slide
      # Q3: the slide is shown with nothing selected
      And the slide "Slide 1" is shown, and the chart fills its frame
      And the chart on it is called "Sales"
      And nothing is selected
      And instead of the formula bar there are the tools Text, Image, Circle, Rectangle and Triangle
      And there are no speaker notes and there is no Present

    Scenario: One undo takes the slide and its chart away
      When I insert a bar chart "Sales" of A1:B4 as a slide
      And I undo
      Then the tabs read "Sheet1"
      And Sheet1 is shown
      And the history shows one entry for the chart

    Scenario: The chart on a slide follows its cells
      When I insert a bar chart "Sales" of A1:B4 as a slide
      And I change B2 on Sheet1 to 150
      Then the bar of East on the slide "Slide 1" is 150 high

  @extended
  Rule: A floating chart on the sheet is made as before

    Scenario: A floating object on the sheet
      When I insert a bar chart "Sales" of A1:B4 as a floating object on the sheet
      Then the chart "Sales" is on Sheet1, at the selected cells
      And the tabs read "Sheet1"

  @extended
  Rule: While a slide is shown, Insert ▸ Chart… puts the chart on that slide or on a new one

    # Step 3, owner 2026-11-23 (Q3)
    Background:
      Given I inserted a bar chart "Sales" of A1:B4 as a slide

    Scenario: The dialog offers "On this slide" instead of the sheet
      When I choose Insert ▸ Chart… while the slide "Slide 1" is shown
      Then the dialog offers to show the chart as "A slide" or "On this slide"

  # ================================================================ Move to Slide

  @core @firefox
  Rule: "Move to Slide" puts a chart on a sheet onto a slide of its own

    Background:
      Given a bar chart "Sales" of A1:B4 floats on Sheet1

    Scenario: The object menu of a chart offers "Move to Slide"
      When I open the object menu of the chart
      Then it offers "Name & Describe…", "Reference in Chat", "Style…", "Cut", "Copy", "Delete" and "Move to Slide"

    Scenario: The chart moves to a new slide and keeps its name
      # Q1: the chart keeps the name people may already use for it; the new slide gets the next free "Slide N"
      When I choose "Move to Slide" in the object menu of the chart
      Then the tabs read "Sheet1", "Slide 1"
      And the slide "Slide 1" is shown, and the chart fills its frame
      And the chart on it is still called "Sales"
      And Sheet1 has no chart

    Scenario: One undo puts the chart back where it was
      # Q4
      When I choose "Move to Slide" in the object menu of the chart
      And I undo
      Then the chart floats on Sheet1 at the place and in the size it had
      And the tabs read "Sheet1"
      And Sheet1 is shown

    @extended @two-users
    Scenario: Undoing the move keeps the slide when a colleague put something on it
      # Q4: the slide goes with the undo only when it is empty
      Given Ben, an editor, has the document open
      When I choose "Move to Slide" in the object menu of the chart
      And Ben adds a text box saying "Note" to the slide "Slide 1"
      And I undo
      Then the chart floats on Sheet1 at the place and in the size it had
      And the tabs read "Sheet1", "Slide 1"
      And the slide "Slide 1" shows the text box "Note"

  # ================================================================ more on a slide

  @core
  Rule: A slide holds text boxes, shapes and pictures beside its chart

    Scenario: A text box beside the chart stays after the page is loaded again
      Given I inserted a bar chart "Sales" of A1:B4 as a slide
      When I make the chart half as wide
      And I add a text box saying "East leads" beside it with the tool Text
      And I load the page again
      Then the slide "Slide 1" shows the chart and the text box "East leads"

  # ================================================================ the slide goes with its last object

  @core
  Rule: A slide goes with its last object, in the same step

    Background:
      Given I inserted a bar chart "Sales" of A1:B4 as a slide

    Scenario: Deleting the only chart deletes the slide
      # Q2: the tab before it is shown (the one after it, if the slide was the first)
      When I delete the chart
      Then the tabs read "Sheet1"
      And Sheet1 is shown

    Scenario: One undo brings the slide and its chart back
      When I delete the chart
      And I undo
      Then the tabs read "Sheet1", "Slide 1"
      And the slide "Slide 1" shows the chart

    @extended
    Scenario: A slide with a text box left stays
      Given I added a text box saying "East leads" to the slide
      When I delete the chart
      Then the tabs read "Sheet1", "Slide 1"
      When I delete the text box
      Then the tabs read "Sheet1"

  # ================================================================ only through a chart

  @extended
  Rule: Nothing else makes a slide

    Scenario: "+" adds a sheet
      When I press "+" in the strip of tabs
      Then a new sheet is added and shown
      And the Edit menu has no entry that makes a slide

  # ================================================================ names, colleagues, viewers

  @extended
  Rule: A slide is a tab like a sheet

    Scenario: A slide is renamed like a sheet
      Given I inserted a bar chart "Sales" of A1:B4 as a slide
      When I double-click the tab "Slide 1" and type "Q1 sales"
      Then the tabs read "Sheet1", "Q1 sales"

    @two-users
    Scenario: A colleague sees the slide come and go
      Given Ben, an editor, has the document open
      When I insert a bar chart "Sales" of A1:B4 as a slide
      Then Ben's tabs read "Sheet1", "Slide 1"
      When I undo
      Then Ben's tabs read "Sheet1"

    @two-users
    Scenario: A viewer sees the slide and cannot move a chart
      # Q5; since the menus show what fits (D1600, D1603) the entry is left out with the others
      Given Vera, a viewer, has the document open
      And a bar chart "Sales" of A1:B4 floats on Sheet1
      When Vera opens the object menu of the chart
      Then it holds only the greyed line "You can only look at this document."

  # ================================================================ files and print

  @core @io:packages/claudia-computes-io/tests/test_slide_tabs.py
  Rule: A slide is a tab of its own in an xlsx or ods file, with its objects where they were

    # E6.31 step 5 (D1477 to D1479): one slide unit is one pixel of the tab, so a slide of 1600 × 900 covers
    # 1600 × 900 pixels from the tab's corner. The file says in a property which tabs were slides.
    Background:
      Given the slide "Sales chart" holds the chart "Sales" at 100, 50, 800 by 450
      And the text box "East leads" at 1000, 100, 400 by 100
      And the picture "Logo" at 1200, 700, 200 by 100

    Scenario Outline: The objects of a slide are where they were
      When I export the document as <format>
      Then the file has the tabs "Sheet1" and "Sales chart", and "Sales chart" has no cells
      And on "Sales chart" the chart is at 100, 50, 800 by 450 pixels from the corner of the tab
      And the text box is at 1000, 100, 400 by 100, saying "East leads" in the look of its style
      And the picture is at 1200, 700, 200 by 100
      And I am told nothing about the slide
      Examples:
        | format |
        | xlsx   |
        | ods    |

    Scenario Outline: A slide comes back as a slide
      Given the document was exported as <format>
      When I import the file
      Then the tabs read "Sheet1", "Sales chart", and "Sales chart" is a slide
      And the chart, the text box and the picture are where they were, as big, with the styles they had
      Examples:
        | format |
        | xlsx   |
        | ods    |

  @extended @io:packages/claudia-computes-io/tests/test_slide_tabs.py
  Rule: A tab that no longer fits the mark is a sheet

    Scenario: The tab was renamed in another program
      Given an xlsx file written from a workbook with the slide "Sales chart"
      And the tab was renamed "Chart tab" in another program
      When I import it
      Then "Chart tab" is a sheet with the chart and the picture floating on it where they were
      And the text box is reported as not shown, as one on a sheet is

    Scenario: Someone typed into the tab in another program
      Given an ods file written from a workbook with the slide "Sales chart"
      And someone typed "note" into A1 of "Sales chart" in another program
      When I import it
      Then "Sales chart" is a sheet with "note" in A1 and the chart and the picture floating on it

  @extended
  Rule: A slide is printed as a page of its own

    Scenario: Printing while a slide is shown
      # Q7
      Given I inserted a bar chart "Sales" of A1:B4 as a slide
      When I open the print preview
      Then it shows one landscape page with the chart, as a slide in creates is printed

    Scenario: Printing the whole workbook puts the slide between the sheets
      # Q7
      Given there is a second sheet "Costs"
      And I inserted a bar chart "Sales" of A1:B4 as a slide while Sheet1 was shown
      When I print the whole workbook
      Then the pages are Sheet1, the slide "Slide 1" on a landscape page, then Costs

    @e2e:computes-slides.cjs
    Scenario: The print bar speaks of the slide shown as a slide
      # UX-73
      Given the slide "Sales chart" is shown
      When I open the print preview
      Then "Contents" offers "This slide", "Whole workbook"
      When I print the whole workbook
      Then the status line counts 2 sheets and 1 slide

  # ================================================================ search

  @extended @e2e:computes-slides.cjs
  Rule: Search looks at the words on the slides too

    Scenario: A word on a slide is found and shown
      # UX-72
      Given the slide "Sales chart" has a text box saying "East leads"
      And Sheet1 is shown
      When I search for "East" in all sheets and slides
      Then a match is listed in "Sales chart" and one in Sheet1!A2
      When I go to the match in "Sales chart"
      Then the slide "Sales chart" is shown with the match marked in the text box

    Scenario: With a slide shown, "This slide" searches only that slide
      # UX-72
      Given the slide "Sales chart" is shown
      When I search for "East" in this slide
      Then the only match is in the text box of "Sales chart"

    Scenario: A replacement changes the words on a slide in the same step as the cells
      # UX-72
      Given Sheet1 is shown
      When I replace "East" with "Ost" in all sheets and slides
      Then Sheet1!A2 reads "Ost" and the text box on "Sales chart" says "Ost leads"
      When I undo
      Then both read "East" again
