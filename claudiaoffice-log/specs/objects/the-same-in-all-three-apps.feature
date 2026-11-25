# Objects, styles and the palette behave alike in all three apps; a viewer is told at once that she can only look
# (D1431, D1432, CODE-75). Reviewed by the owner 2026-11-22; the chart-tab scenario waits for the chart renames of E1.18.
Feature: Objects, styles and the palette work the same in a text, a workbook and a presentation

  # -- a viewer --------------------------------------------------------------------------------------------
  # UX-69: today a viewer's greyed entries and object gestures are silent; she is not told.
  @core @app:composes @app:computes @app:creates @pending:UX-69
  Scenario Outline: A viewer who tries to change something is told she can only look, and nothing is sent
    Given a <document> that I may only view
    When I try to <change>
    Then I am told "You can only look at this document."
    And the document is as it was
    And my colleague sees no change and no message

    Examples:
      | document     | change                                  |
      | text         | insert a picture                        |
      | workbook     | insert a picture                        |
      | presentation | insert a picture                        |
      | text         | insert a container                      |
      | workbook     | insert a container                      |
      | presentation | insert a container                      |
      | text         | rename a style                          |
      | workbook     | rename a style                          |
      | presentation | rename a style                          |
      | text         | move, resize, turn or delete an object  |
      | workbook     | move, resize, turn or delete an object  |
      | presentation | move, resize, turn or delete an object  |
      | text         | change a colour of the palette          |
      | workbook     | change a colour of the palette          |
      | presentation | change a colour of the palette          |

  # -- two people ------------------------------------------------------------------------------------------
  @core @two-users @app:composes @app:computes @app:creates
  Scenario Outline: What one person does to an object, a style or the palette, the other sees at once
    Given a <document> open by me and by a colleague
    When I <change>
    Then my colleague sees it without reloading
    And after a reload we both see the same

    Examples:
      | document     | change                                   |
      | text         | insert a picture                         |
      | workbook     | insert a picture                         |
      | presentation | insert a picture                         |
      | text         | insert a shape                           |
      | presentation | insert a shape                           |
      | text         | move a container                         |
      | workbook     | move a container                         |
      | presentation | move a container                         |
      | text         | rename a style                           |
      | workbook     | rename a style                           |
      | presentation | rename a style                           |
      | text         | change a colour of the palette           |
      | workbook     | change a colour of the palette           |
      | presentation | change a colour of the palette           |

  # Approved by the owner on 2026-11-25 (UX-84, D1223).
  @core @two-users @app:composes @app:computes @app:creates
  Scenario Outline: What I have selected, a colleague sees in my colour with my name, and cannot change
    Given a <document> open by me and by a colleague
    And a picture in it
    When I select the picture
    Then my colleague sees my colour round it and my name
    When my colleague tries to move it
    Then she is told that I am working on it
    And it stays where it is for both of us
    When I let go of it
    Then my colleague no longer sees my name on it

    Examples:
      | document     |
      | text         |
      | workbook     |
      | presentation |

  # -- what an object shows, kept in the document ------------------------------------------------------------
  @core @app:composes @app:computes @app:creates
  Scenario Outline: Undo and redo of inserting an object take what it shows with it
    Given a <document>
    When I insert <an object>
    And I undo
    Then the object is gone, and the document no longer keeps what it showed
    When I redo
    Then the object is back and shows the same as before

    Examples:
      | document     | an object      |
      | text         | a picture      |
      | workbook     | a picture      |
      | presentation | a picture      |
      | text         | a container    |
      | workbook     | a container    |
      | presentation | a container    |
      | presentation | a shape        |
      | workbook     | a chart        |
