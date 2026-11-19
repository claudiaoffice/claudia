# Every thing has a name (D550, D554, D1303–D1305, D1310, D1312)
Feature: A person can point at anything by its name, change the name, and come back to where she was

  # -- a name from the start ------------------------------------------------------------------------------
  @core @app:composes @pending:e1.13
  Scenario: A new paragraph has a name of its own
    Given a text with two paragraphs
    When I add a third paragraph
    Then Name & describe… on it shows a name like "Paragraph 3"
    And the name is in my own language

  @core @app:composes @app:computes @app:creates
  Scenario: A new object, slide, sheet and chart tab have names
    Given a new document
    When I add a text box, or a slide, or a sheet, or a chart
    Then each has a name like "Text box 1", "Slide 2", "Sheet 2", "Chart 1"
    And two things never have the same name

  @core @app:composes @app:creates @pending:e1.13
  Scenario: Importing a file names everything that the file does not name
    Given a presentation or a text file whose slides, objects and paragraphs have no names
    When I import it
    Then every slide, object and paragraph has a name like "Slide 1", "Picture 2", "Paragraph 7"
    And what the file does name keeps its name; a name that occurs twice gets "(2)" on the later one

  # -- the dialog -----------------------------------------------------------------------------------------
  @core @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: Name & describe… has a name field
    Given a picture is selected
    When I choose Edit ▸ Name & describe…
    Then the dialog shows the name, the description and "Decorative"
    When I change the name to "Logo" and save
    Then the picture is called "Logo" in the # list of the chat
    And the history shows one entry "Rename"

  @core @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: The right-click menu opens the same dialog
    Given a text box is on the page
    When I press the right button on it and choose "Name & describe…"
    Then I see the same dialog as from the Edit menu, with the name field

  @core @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: A name that is taken is refused in words
    Given a text called "Intro" and a picture
    When I give the picture the name "intro" and save
    Then the dialog stays open with my entry and says "There is already a text called “Intro”"

  @extended @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: Undo gives the old name back
    Given I renamed a picture from "Picture 1" to "Logo"
    When I undo
    Then the picture is called "Picture 1" again

  @core @two-users @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: The other person sees the new name at once
    Given ann and ben have the document open
    When ann renames a picture to "Logo"
    Then ben sees "Logo" in his # list, and a tag ann wrote earlier now reads "Logo"

  @core @app:composes @needs-decision
  Scenario: A paragraph is renamed in the same dialog, without a description
    Given the caret is in a paragraph
    When I choose Edit ▸ Name & describe…
    Then the dialog has the name field and no description and no "Decorative"

  @extended @app:composes @needs-decision
  Scenario: A heading is called by its title
    Given a heading "Introduction"
    When I open Name & describe… on it
    Then the name is "Introduction" and cannot be changed there

  @extended @app:composes @needs-decision
  Scenario: Splitting and joining paragraphs
    Given a paragraph called "Paragraph 3"
    When I split it in the middle
    Then the first part is still "Paragraph 3" and the second has a new name
    When I join them again
    Then the paragraph is "Paragraph 3", and Undo brings the second name back

  # -- the way back ---------------------------------------------------------------------------------------
  @core @app:composes @pending:e1.13
  Scenario: A tag to a far-away paragraph takes me there, and I can come back
    Given I am reading page 2 of a long text
    And a colleague's chat message points at a paragraph on page 40
    When I click the tag
    Then the text shows that paragraph, marked for a moment
    And a "← Back where I was" is offered
    When I use it
    Then I am reading page 2 again, at the line where I was

  @core @app:computes @pending:e1.13
  Scenario: The same in a sheet, within one sheet
    Given I am looking at the top of a long sheet
    And a tag points at a named range far down in it
    When I click the tag and then "← Back where I was"
    Then I see the top of the sheet again

  @extended @app:composes @app:computes @app:creates @needs-decision
  Scenario: The way back stays until I use it or start working
    Given a tag took the view away
    When I wait a minute
    Then "← Back where I was" is still offered
    When I type, or click into the document
    Then it is gone

  @extended @app:composes @app:computes @app:creates @needs-decision
  Scenario: The way back is reachable when the History & Chat panel is folded away
    Given the panel is hidden and a tag has taken the view away
    When I choose View ▸ Back where I was
    Then the view returns to where I was
