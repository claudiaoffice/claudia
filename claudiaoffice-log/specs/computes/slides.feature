# Slides in computes
Feature: Slides in computes (E6.31)
  As someone who builds charts in a workbook, I want a slide among my sheets that holds a chart together with text
  boxes and shapes, so that a chart can have a page of its own with words beside it, and works like a slide in creates.
  A slide comes into existence only for a chart, and goes with its last object. The screens are
  `notes/mockups/computes-slides-*.svg`, the architecture `notes/e6-31-slides-in-computes.md`. The owner's answers
  to the review of 2026-11-22 are written into the scenarios (`Q<n>` names the question they answer); the decisions
  are D1470 to D1473.
  What every object does (selecting, moving, scaling, naming, the object menu as such) is in `specs/objects/` and is
  not repeated here.

  Background:
    Given a new computes document "sales" in which I am Ann, an owner
    And Sheet1 has "Region" and "Amount" in A1 and B1, and East 300, West 120 and North 70 below them

  # ================================================================ a chart as a slide

  @core @firefox
  Rule: Edit ▸ Chart… shows a chart as a slide of its own, right after the tab I am on

    Scenario: "A slide" is what the dialog offers first
      When I select A1:B4 and choose Edit ▸ Chart…
      Then the dialog offers to show the chart as "A slide" or as "A floating object on the sheet"
      And "A slide" is chosen
      And the name field asks for "the slide it opens as"

    Scenario: The chart becomes a slide, right after the sheet I am on
      Given there is a second sheet "Costs"
      When I insert a bar chart of A1:B4 as a slide named "Sales chart"
      Then the tabs read "Sheet1", "Sales chart", "Costs"
      And the tab "Sales chart" is marked as a slide
      # Q3: the slide is shown with nothing selected
      And the slide "Sales chart" is shown, and the chart fills its frame
      And nothing is selected
      And instead of the formula bar there are the tools Text, Image, Circle, Rectangle and Triangle
      And there are no speaker notes and there is no Present

    Scenario: One undo takes the slide and its chart away
      When I insert a bar chart of A1:B4 as a slide named "Sales chart"
      And I undo
      Then the tabs read "Sheet1"
      And Sheet1 is shown
      And the history shows one entry for the chart

    Scenario: The chart on a slide follows its cells
      When I insert a bar chart of A1:B4 as a slide named "Sales chart"
      And I change B2 on Sheet1 to 150
      Then the bar of East on the slide "Sales chart" is 150 high

  @extended
  Rule: A floating chart on the sheet is made as before

    Scenario: A floating object on the sheet
      When I insert a bar chart of A1:B4 as a floating object on the sheet
      Then the chart is on Sheet1, at the selected cells
      And the tabs read "Sheet1"

  # ================================================================ Move to Slide

  @core @firefox
  Rule: "Move to Slide" puts a chart on a sheet onto a slide of its own

    Background:
      Given a bar chart "Sales" of A1:B4 floats on Sheet1

    Scenario: The object menu of a chart offers "Move to Slide"
      When I open the object menu of the chart
      Then it offers "Name & describe…", "Style…", "Move to Slide" and "Delete"

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
      Given I inserted a bar chart of A1:B4 as a slide named "Sales chart"
      When I make the chart half as wide
      And I add a text box saying "East leads" beside it with the tool Text
      And I load the page again
      Then the slide "Sales chart" shows the chart and the text box "East leads"

  # ================================================================ the slide goes with its last object

  @core
  Rule: A slide goes with its last object, in the same step

    Background:
      Given I inserted a bar chart of A1:B4 as a slide named "Sales chart"

    Scenario: Deleting the only chart deletes the slide
      # Q2: the tab before it is shown (the one after it, if the slide was the first)
      When I delete the chart
      Then the tabs read "Sheet1"
      And Sheet1 is shown

    Scenario: One undo brings the slide and its chart back
      When I delete the chart
      And I undo
      Then the tabs read "Sheet1", "Sales chart"
      And the slide "Sales chart" shows the chart

    @extended
    Scenario: A slide with a text box left stays
      Given I added a text box saying "East leads" to the slide
      When I delete the chart
      Then the tabs read "Sheet1", "Sales chart"
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
      Given I inserted a bar chart of A1:B4 as a slide named "Sales chart"
      When I double-click the tab "Sales chart" and type "Q1 sales"
      Then the tabs read "Sheet1", "Q1 sales"

    @two-users
    Scenario: A colleague sees the slide come and go
      Given Ben, an editor, has the document open
      When I insert a bar chart of A1:B4 as a slide named "Sales chart"
      Then Ben's tabs read "Sheet1", "Sales chart"
      When I undo
      Then Ben's tabs read "Sheet1"

    @two-users
    Scenario: A viewer sees the slide and cannot move a chart
      # Q5
      Given Vera, a viewer, has the document open
      And a bar chart "Sales" of A1:B4 floats on Sheet1
      When Vera opens the object menu of the chart
      Then "Move to Slide" is there but cannot be chosen

  # ================================================================ files and print

  @extended @io:packages/claudia-computes-io/tests/test_slide_plan.py
  Rule: A slide is written to ods and xlsx as a sheet with its objects on it

    Scenario: Downloading as xlsx or ods says that a slide became a sheet
      # Q6
      Given I inserted a bar chart of A1:B4 as a slide named "Sales chart"
      When I export the document as xlsx
      Then the file has the sheets "Sheet1" and "Sales chart", and the chart is on "Sales chart"
      And I am told "The slide “Sales chart” was written as a sheet: a workbook in this format has no slides."

    Scenario: Read back, what was a slide is a sheet
      Given an xlsx file written from a workbook with the slide "Sales chart"
      When I import it
      Then the tabs read "Sheet1", "Sales chart"
      And "Sales chart" is a sheet with the chart floating on it

  @extended
  Rule: A slide is printed as a page of its own

    Scenario: Printing while a slide is shown
      # Q7
      Given I inserted a bar chart of A1:B4 as a slide named "Sales chart"
      When I open the print preview
      Then it shows one landscape page with the chart, as a slide in creates is printed

    Scenario: Printing the whole workbook puts the slide between the sheets
      # Q7
      Given there is a second sheet "Costs"
      And I inserted a bar chart of A1:B4 as a slide named "Sales chart" while Sheet1 was shown
      When I print the whole workbook
      Then the pages are Sheet1, the slide "Sales chart" on a landscape page, then Costs

    @e2e:computes-slides
    Scenario: The print bar speaks of the slide shown as a slide
      # UX-73
      Given the slide "Sales chart" is shown
      When I open the print preview
      Then "Contents" offers "This slide", "Whole workbook"
      When I print the whole workbook
      Then the status line counts 2 sheets and 1 slide

  # ================================================================ search

  @extended @e2e:computes-slides
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
