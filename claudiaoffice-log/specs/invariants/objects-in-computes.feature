# What is always true of an object on a computes sheet (the composes invariants, for computes; bug eater batch 4)
@draft @invariant
Feature: Every object on a computes sheet behaves like an object
  Whatever kind of object a person puts on a sheet, a few things are always true. They are written once here and run for
  each kind; a new kind of object is added as a row of `Examples` and must pass all of them before it is called done. The
  pilot has the chart and the picture, the two kinds computes makes today.

  Background:
    Given a new computes workbook "budget" in which I am Ann, an owner
    And the sheet "Sheet1" has the numbers 4, 8 and 15 in A1:A3
    And B5 is selected

  # ---------------------------------------------------------------- it is there once

  @core @firefox
  Scenario Outline: A new <kind> is shown exactly once
    When I insert a <kind>
    Then the <kind> is shown once, on "Sheet1", with its top left corner at B5
    And the <kind> is in the list of things I can refer to with "#" in the chat, once
    And the cells A1:A3 are as they were

    Examples:
      | kind    |
      | chart   |
      | picture |

  @core @firefox
  Scenario Outline: A <kind> is still there once after the page is reloaded
    Given I have inserted a <kind>
    When I reload the page and open "budget" again
    Then the <kind> is shown once, on "Sheet1", at B5

    Examples:
      | kind    |
      | chart   |
      | picture |

  @core
  Scenario Outline: A <kind> is still there once after the connection drops and comes back
    Given I have inserted a <kind>
    When the connection to the server is lost and comes back
    Then the <kind> is shown once, on "Sheet1", at B5
    And I can still select and move the <kind>

    Examples:
      | kind    |
      | chart   |
      | picture |

  @extended
  Scenario Outline: A <kind> is shown on its own sheet only, and once in the print preview
    Given I have inserted a <kind>
    When I go to another sheet and back
    Then the <kind> is shown once, on "Sheet1" only
    When I open the print preview
    Then the <kind> is shown once on the pages

    Examples:
      | kind    |
      | chart   |
      | picture |

  # ---------------------------------------------------------------- I can work with it

  @core
  Scenario Outline: I can work with a new <kind> straight away
    When I insert a <kind>
    Then I can select, move and resize the <kind> with the mouse
    And I can reach the <kind>, move it and leave it again with the keyboard alone
    And what I did is shown on the <kind> and nowhere else on the sheet

    Examples:
      | kind    |
      | chart   |
      | picture |

  @core
  Scenario Outline: Typing in the cells around a <kind> does not move or copy it
    Given I have inserted a <kind>
    When I type 16 into A4 and "Total" into B4
    Then the <kind> is shown once, on "Sheet1", at B5

    Examples:
      | kind    |
      | chart   |
      | picture |

  # ---------------------------------------------------------------- history

  @core @firefox
  Scenario Outline: Undo takes a <kind> away, redo brings it back
    Given I have inserted a <kind>
    When I undo
    Then there is no <kind> on the sheet
    When I redo
    Then the <kind> is shown once, on "Sheet1", at B5
    And the history shows one entry for adding it

    Examples:
      | kind    |
      | chart   |
      | picture |

  @core
  Scenario Outline: A removed <kind> is gone everywhere, and undo brings it back as it was
    Given I have inserted a <kind> and moved it to D7
    When I remove the <kind>
    Then there is no <kind> on the sheet, in the "#" list, or in the print preview
    When I reload the page and open "budget" again
    Then there is no <kind> on the sheet
    When I undo
    Then the <kind> is shown once, at D7

    Examples:
      | kind    |
      | chart   |
      | picture |

  # ---------------------------------------------------------------- other people

  @core @two-users
  Scenario Outline: A colleague sees a new <kind> once, and sees where I move it
    Given Ben, an editor, has the workbook open as well
    When I insert a <kind> and move it to D7
    Then Ben sees the <kind> once, on "Sheet1", at D7
    When Ben reloads the page
    Then Ben sees the <kind> once

    Examples:
      | kind    |
      | chart   |
      | picture |

  @extended @two-users
  Scenario Outline: A reader can see a <kind> but not change it
    Given I have inserted a <kind>
    And Cleo, a reader, has the workbook open
    Then Cleo sees the <kind> once
    And Cleo cannot move, resize or remove the <kind>
    And the entries for changing a <kind> are not offered to Cleo or are shown as unavailable

    Examples:
      | kind    |
      | chart   |
      | picture |

  # ---------------------------------------------------------------- names and description

  @extended
  Scenario Outline: A <kind> has a name nobody else has, and a description for people who cannot see it
    When I insert a <kind>
    Then the <kind> has a name
    And that name is different from the name of every other thing in the workbook, the sheets included
    When I give it a description
    Then a screen reader reads the <kind> by its name and its description

    Examples:
      | kind    |
      | chart   |
      | picture |

  # ---------------------------------------------------------------- files

  @extended
  Scenario Outline: A <kind> survives saving as <format> and opening that file as a new workbook
    Given I have inserted a <kind>, moved it to D7 and given it the name "Mine"
    When I export the workbook as <format> and open that file as a new workbook
    Then the new workbook has the <kind> once, on "Sheet1", at D7, called "Mine"

    Examples:
      | kind    | format       |
      | chart   | OpenDocument |
      | chart   | Excel        |
      | picture | OpenDocument |
      | picture | Excel        |

  @extended
  Scenario Outline: A <kind> added to an opened <format> file is in that file when it is saved again
    Given I opened a <format> file with numbers in A1:A3 and kept the file
    When I insert a <kind> at B5 and export the workbook as <format>
    Then the file has the <kind> once, on its first sheet, at B5
    And the Export dialog does not say that the <kind> is not in the file

    Examples:
      | kind    | format       |
      | chart   | OpenDocument |
      | chart   | Excel        |
      | picture | OpenDocument |
      | picture | Excel        |
