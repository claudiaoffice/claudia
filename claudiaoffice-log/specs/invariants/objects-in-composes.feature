@invariant
Feature: Every object in a composes text behaves like an object
  Whatever kind of object a person puts into a text, a few things are always true. They are written once here and run
  for each kind; a new kind of object (text box, picture, shape, diagram, table of contents, ...) is added as a row of
  `Examples` and must pass all of them before it is called done. The pilot has the table only.

  Background:
    Given a new composes document "report" in which I am Ann, an owner
    And the text has the paragraphs "Before" and "After"
    And my caret is at the end of "Before"

  # ---------------------------------------------------------------- it is there once

  @core @firefox
  Scenario Outline: A new <kind> is shown exactly once
    When I insert a <kind>
    Then the <kind> is shown once, between "Before" and "After"
    And the <kind> is in the list of things I can refer to with "#" in the chat, once
    And the paragraphs "Before" and "After" are as they were

    Examples:
      | kind  |
      | table |

  @core @firefox
  Scenario Outline: A <kind> is still there once after the page is reloaded
    Given I have inserted a <kind>
    When I reload the page and open "report" again
    Then the <kind> is shown once, between "Before" and "After"

    Examples:
      | kind  |
      | table |

  @core
  Scenario Outline: A <kind> is still there once after the connection drops and comes back
    Given I have inserted a <kind>
    When the connection to the server is lost and comes back
    Then the <kind> is shown once, between "Before" and "After"
    And I can still work in the <kind>

    Examples:
      | kind  |
      | table |

  @extended
  Scenario Outline: A <kind> is shown once in every view
    Given I have inserted a <kind>
    When I switch to the page view
    Then the <kind> is shown once
    When I open the print preview
    Then the <kind> is shown once on the pages
    When I switch back to the flow view
    Then the <kind> is shown once

    Examples:
      | kind  |
      | table |

  # ---------------------------------------------------------------- I can work in it

  @core @firefox
  Scenario Outline: I can work in a new <kind> straight away
    When I insert a <kind>
    Then I can work in the <kind> with the mouse
    And I can work in the <kind> with the keyboard alone, and leave it again with the keyboard alone
    And what I did is shown in the <kind> and nowhere else on the page

    Examples:
      | kind  |
      | table |

  @core
  Scenario Outline: Typing before and after a <kind> does not move or copy it
    Given I have inserted a <kind>
    When I type " and more" at the end of "Before"
    And I type "First " at the start of "After"
    Then the <kind> is shown once, between "Before and more" and "First After"

    Examples:
      | kind  |
      | table |

  # ---------------------------------------------------------------- history

  @core @firefox
  Scenario Outline: Undo takes a <kind> away, redo brings it back
    Given I have inserted a <kind>
    When I undo
    Then there is no <kind> in the text
    When I redo
    Then the <kind> is shown once, between "Before" and "After"
    And the history shows one entry for adding it

    Examples:
      | kind  |
      | table |

  @core
  Scenario Outline: A removed <kind> is gone everywhere, and undo brings it back as it was
    Given I have inserted a <kind> and worked in it
    When I remove the <kind>
    Then there is no <kind> in the text, in the "#" list, or in the print preview
    When I reload the page and open "report" again
    Then there is no <kind> in the text
    When I undo
    Then the <kind> is shown once as I left it

    Examples:
      | kind  |
      | table |

  # ---------------------------------------------------------------- other people

  @core @two-users
  Scenario Outline: A colleague sees a new <kind> once, and sees what I do in it
    Given Ben, an editor, has the document open as well
    When I insert a <kind> and work in it
    Then Ben sees the <kind> once, between "Before" and "After", as I left it
    When Ben reloads the page
    Then Ben sees the <kind> once

    Examples:
      | kind  |
      | table |

  @extended @two-users
  Scenario Outline: A reader can see a <kind> but not change it
    Given I have inserted a <kind> and worked in it
    And Cleo, a reader, has the document open
    Then Cleo sees the <kind> once
    And Cleo cannot change anything in the <kind>
    And the entries for changing a <kind> are not offered to Cleo or are shown as unavailable

    Examples:
      | kind  |
      | table |

  # ---------------------------------------------------------------- names and description

  @extended
  Scenario Outline: A <kind> has a name nobody else has, and a description for people who cannot see it
    When I insert a <kind>
    Then the <kind> has a name
    And that name is different from the name of every other thing in the document
    When I give it a description
    Then a screen reader reads the <kind> by its name and its description

    Examples:
      | kind  |
      | table |

  # ---------------------------------------------------------------- files

  @extended
  Scenario Outline: A <kind> survives saving as <format> and opening that file as a new document
    Given I have inserted a <kind> and worked in it
    When I download the document as <format> and open that file as a new document
    Then the new document has the <kind> once, between "Before" and "After", with what I put in it

    Examples:
      | kind  | format       |
      | table | OpenDocument |
      | table | Word         |
