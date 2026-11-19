# Every thing has a name and can be described; a tag leaves a way back
# (D550, D551, D554, D1303–D1305, D1310–D1312, D1317). Answers: names.review.md, 2026-11-19.
Feature: A person can point at anything by its name, change the name, describe it, and come back to where she was

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

  @extended @app:composes @pending:e1.13
  Scenario: A paragraph inserted between two others takes the first free number
    Given paragraphs called "Paragraph 1", "Paragraph 2" and "Paragraph 3" in this order
    When I insert a paragraph between the first and the second
    Then it is called "Paragraph 4" and the others keep their names

  @core @app:composes @app:creates @pending:e1.13
  Scenario: Importing a file names everything that the file does not name
    Given a presentation or a text file whose slides, objects and paragraphs have no names
    When I import it
    Then every slide, object and paragraph has a name like "Slide 1", "Picture 2", "Paragraph 7"
    And what the file does name keeps its name; a name that occurs twice gets "(2)" on the later one

  @core @app:composes @pending:e1.13
  Scenario: A bookmark around one paragraph becomes its name on import
    Given a Word file with a bookmark "Terms" around exactly one paragraph
    When I import it
    Then that paragraph is called "Terms"

  @core @app:composes @pending:e1.13
  Scenario: Export writes a bookmark only for a name a person gave
    Given a text with 500 paragraphs of which one was renamed "Terms" by a person
    When I export it as a Word file
    Then the file holds one bookmark, "Terms", around that paragraph
    And no bookmark for the paragraphs that still have their generic names

  # -- the dialog ----------------------------------------------------------------------------------------
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

  @core @app:composes @pending:e1.13
  Scenario: A person gives a paragraph a name of her own
    Given the caret is in a paragraph called "Paragraph 3"
    When I choose Edit ▸ Name & describe…, change the name to "Terms" and save
    Then the paragraph is called "Terms"
    And an older tag in the chat to that paragraph reads "Terms", and so does the history

  @core @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: Everything can be described, a paragraph and a range too
    Given the caret is in a paragraph (or a range of cells is selected)
    When I choose Edit ▸ Name & describe…
    Then the dialog has a name field and a description field
    And it has no "Decorative" tick, which only a picture, chart, shape or text box has
    When I type a description and save
    Then the dialog shows it again the next time I open it

  @extended @app:composes @pending:e1.13
  Scenario: A heading is called by its title
    Given a heading "Introduction"
    When I open Name & describe… on it
    Then the name is "Introduction" and cannot be changed there
    And the description can

  @extended @app:composes @pending:e1.13
  Scenario: Two headings with the same title
    Given two headings that both read "Introduction"
    Then the second is shown as "Introduction (2)" in the # list
    And the text of the heading is unchanged

  @extended @app:composes @pending:e1.13
  Scenario: Splitting and joining paragraphs
    Given a paragraph called "Paragraph 3"
    When I split it in the middle
    Then the first part is still "Paragraph 3" and the second has a new name
    When I join them again
    Then the paragraph is "Paragraph 3", and Undo brings the second name back

  # -- pointing -------------------------------------------------------------------------------------------
  @core @app:composes @pending:e1.13
  Scenario: The # list in a long text
    Given a text of 300 paragraphs of which one is renamed "Terms", and a heading "Introduction"
    When I type # in the chat
    Then the list offers the paragraphs in my view as "Paragraph 12 · first words of the text"
    And always "Terms" and "Introduction", wherever they are
    When I type "ter"
    Then the list is filtered across the whole document

  @core @app:composes @pending:e1.13
  Scenario: A tag to a paragraph that has been deleted shows the document as it was
    Given a tag in the chat to a paragraph that a colleague has since deleted
    When I click the tag
    Then I see the text as it was when the paragraph last existed, as a replay, with the paragraph marked
    And nothing in the document has changed

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

  @core @app:creates @pending:e1.13
  Scenario: The same between slides
    Given I am on slide 2
    When I click a tag that points at an object on slide 9, and then "← Back where I was"
    Then I am on slide 2 again

  @core @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: The way back stays until I use it or start working
    Given a tag took the view away
    When I wait a minute
    Then "← Back where I was" is still offered
    When I type, or click into the document
    Then it is gone

  @extended @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: Jumping again replaces the way back
    Given a tag took the view from place A to place B, and I have not used the way back
    When I click a second tag that takes me to place C
    Then "Back where I was" leads to place B, not to A

  @core @app:composes @app:computes @app:creates @pending:e1.13
  Scenario: The way back is reachable when the History & Chat panel is folded away
    Given the panel is hidden and a tag has taken the view away
    When I choose View ▸ Back where I was, or press Ctrl+Shift+B
    Then the view returns to where I was
