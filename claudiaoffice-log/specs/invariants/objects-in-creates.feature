# What is always true of an object on a creates slide (the composes invariants, for creates; bug eater batch 4)
@draft @invariant
Feature: Every object on a creates slide behaves like an object
  Whatever kind of object a person puts on a slide, a few things are always true. They are written once here and run
  for each kind; a new kind of object is added as a row of `Examples` and must pass all of them before it is called
  done. The pilot has the text box, the shape and the picture.

  Background:
    Given a new creates presentation "pitch" in which I am Ann, an owner
    And it has the slides "Opening" and "Closing"
    And "Opening" is shown

  # ---------------------------------------------------------------- it is there once

  @core @firefox
  Scenario Outline: A new <kind> is shown exactly once
    When I insert a <kind>
    Then the <kind> is shown once, on "Opening"
    And the thumbnail of "Opening" shows it once, and the one of "Closing" does not
    And the <kind> is in the list of things I can refer to with "#" in the chat, once

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  @core @firefox
  Scenario Outline: A <kind> is still there once after the page is reloaded
    Given I have inserted a <kind>
    When I reload the page and open "pitch" again
    Then the <kind> is shown once, on "Opening", where I left it

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  @core
  Scenario Outline: A <kind> is still there once after the connection drops and comes back
    Given I have inserted a <kind>
    When the connection to the server is lost and comes back
    Then the <kind> is shown once, on "Opening"
    And I can still select and move the <kind>

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  @extended
  Scenario Outline: A <kind> is shown once in every view
    Given I have inserted a <kind>
    When I start the show
    Then the <kind> is shown once on the first slide
    When I end the show and open the print preview
    Then the <kind> is shown once, on the page of "Opening"

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  # ---------------------------------------------------------------- I can work with it

  @core
  Scenario Outline: I can work with a new <kind> straight away
    When I insert a <kind>
    Then I can select, move, resize and turn the <kind> with the mouse
    And I can reach the <kind>, move it and leave it again with the keyboard alone
    And what I did is shown on the <kind> and nowhere else on the slide

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  @core
  Scenario Outline: Going to another slide and back does not move or copy a <kind>
    Given I have inserted a <kind> and moved it
    When I go to "Closing" and back to "Opening"
    Then the <kind> is shown once, on "Opening", where I left it
    And there is no <kind> on "Closing"

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  # ---------------------------------------------------------------- history

  @core @firefox
  Scenario Outline: Undo takes a <kind> away, redo brings it back
    Given I have inserted a <kind>
    When I undo
    Then there is no <kind> on "Opening"
    When I redo
    Then the <kind> is shown once, on "Opening"
    And the history shows one entry for adding it

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  @core
  Scenario Outline: A removed <kind> is gone everywhere, and undo brings it back as it was
    Given I have inserted a <kind> and moved it
    When I remove the <kind>
    Then there is no <kind> on the slide, in its thumbnail, in the "#" list, or in the print preview
    When I reload the page and open "pitch" again
    Then there is no <kind> on "Opening"
    When I undo
    Then the <kind> is shown once, where I had moved it

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  # ---------------------------------------------------------------- other people

  @core @two-users
  Scenario Outline: A colleague sees a new <kind> once, and sees where I move it
    Given Ben, an editor, has the presentation open as well
    When I insert a <kind> and move it
    Then Ben sees the <kind> once, on "Opening", where I left it
    When Ben reloads the page
    Then Ben sees the <kind> once

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  @extended @two-users
  Scenario Outline: A reader can see a <kind> but not change it
    Given I have inserted a <kind>
    And Cleo, a reader, has the presentation open
    Then Cleo sees the <kind> once
    And Cleo cannot move, resize, turn or remove the <kind>
    And the entries for changing a <kind> are not offered to Cleo or are shown as unavailable

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  # ---------------------------------------------------------------- names and description

  @extended
  Scenario Outline: A <kind> has a name nobody else has, and a description for people who cannot see it
    When I insert a <kind>
    Then the <kind> has a name
    And that name is different from the name of every other thing in the presentation, the slides included
    When I give it a description
    Then a screen reader reads the <kind> by its name and its description

    Examples:
      | kind     |
      | text box |
      | shape    |
      | picture  |

  # ---------------------------------------------------------------- files

  @extended
  Scenario Outline: A <kind> survives saving as <format> and opening that file as a new presentation
    Given I have inserted a <kind>, moved it and given it the name "Mine"
    When I export the presentation as <format> and open that file as a new presentation
    Then the new presentation has the <kind> once, on its first slide, where I left it, called "Mine"

    Examples:
      | kind     | format       |
      | text box | OpenDocument |
      | text box | PowerPoint   |
      | shape    | OpenDocument |
      | shape    | PowerPoint   |
      | picture  | OpenDocument |
      | picture  | PowerPoint   |
