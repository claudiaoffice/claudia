# Pressing, handles and keys of an object in every app (D1221, D1225, D1228, D1390; UX-56, UX-57, UX-58, UX-62, PROC-43)
@e2e:objects.cjs
Feature: A press, a handle and a key belong to the object, or to the dialog on top of it, and to nothing below

  @core
  Scenario: Pressing a handle keeps the object selected
    Given a picture is selected in computes
    When I press a handle, drag it and let go
    Then the picture has its new size, as one entry in the history
    And it is still selected, and the turn handle is still there
    And no cell has been selected under the pointer

  @core
  Scenario: A press on an object leaves the caret of the text where it was
    Given the caret is in a paragraph in composes, and a text box is on the page
    When I press the text box
    Then the text box is selected
    And the caret is in the same paragraph at the same place

  @core
  Scenario: The keys typed in Rotate by… belong to the dialog
    Given an object is selected and Rotate by… is open, in computes or creates
    When I press Backspace in the angle field
    Then the number is edited and the object is still there
    When I give 30 and press Enter
    Then the object is turned to 30° in one entry, and nothing is written in a cell or a text box

  @extended
  Scenario: The left and right arrows nudge an object in composes
    Given a text box is selected in composes
    When I press the right arrow
    Then it is 10 units further to the right, hung from the same character, as one entry
    And with Shift it is one unit further

  @extended
  Scenario: Only what keeps its proportions keeps them
    Given a picture, or a shape with an aspect, shows corner handles only
    When I scale it by a corner
    Then its proportions are kept
    And a Rectangle, which has no aspect, shows the edges as well and may change its proportions

  @extended
  Scenario: A table's menu has its own name
    Given a table is selected in composes
    When I press the right button on its tab
    Then the menu is called "Table menu", and no other menu is open

  @extended
  Scenario: A picture has no words to edit
    Given a picture is selected, in any app
    When I press the right button on it
    Then its menu has no "Edit text"
