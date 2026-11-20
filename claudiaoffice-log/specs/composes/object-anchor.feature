# Where an object in a composes text hangs, and moving it to another paragraph (D1023, D1351, D1352)
Feature: I see where an object hangs and can drag it to any paragraph
  As a writer, I want to see which word an object hangs from, and to drag it anywhere in my text, also into another
  paragraph, so that it stays with the words it belongs to. Mock: notes/mockups/composes-object-anchor-drag.svg.

  Background:
    Given a new composes document "anchors" in which I am Ann, an owner
    And the text has four paragraphs of two lines each
    And I have put a text box in the first paragraph

  # B8 (2026-11-20, size 1): a drop near another paragraph snapped back with "an object cannot change its container".
  @core @firefox
  Rule: An object can be dragged into another paragraph (D1351)

    Scenario: Dropped on the third paragraph, it hangs from it
      When I drag the text box onto the third paragraph and let go
      Then the text box hangs from the third paragraph
      And it stays where I dropped it
      And the history has one entry for the move
      And no message says it could not be done

    Scenario: Undo puts it back where it hung
      Given I have dragged the text box onto the third paragraph
      When I undo
      Then the text box hangs from the first paragraph, where it was

    Scenario: Esc while dragging puts it back and sends nothing
      When I drag the text box onto the third paragraph and press Esc before I let go
      Then the text box hangs from the first paragraph, where it was
      And the history has no entry for a move

  @core @firefox
  Rule: I see the anchor (D1352)

    Scenario: The anchor is shown when the object is selected
      When I select the text box
      Then an anchor mark is drawn at the character it hangs from, in the first paragraph

    Scenario: The anchor moves with the object while I drag it
      When I drag the text box onto the third paragraph without letting go
      Then the anchor mark is in the third paragraph
      And a label says it will hang from "Paragraph 3"
      And the anchor mark is faintly where it was

    Scenario: No anchor mark when nothing is selected
      When I select the text box and press Esc
      Then no anchor mark is drawn

  @extended
  Rule: Tables move the same way (D1351)

    Scenario: A table dragged by its name tab goes after the paragraph it is dropped on
      Given a table of 2 columns and 2 rows after the first paragraph
      When I drag the table by its name tab onto the third paragraph
      Then the table is after the third paragraph
      And no message says it could not be done

  @extended @two-users
  Rule: Colleagues

    Scenario: A colleague sees the object hang from its new paragraph
      Given Ben, an editor, has the document open as well
      When I drag the text box onto the third paragraph and let go
      Then for Ben the text box hangs from the third paragraph

  @unit:packages/claudia-composes/tests/test_text_objects_change_paragraph.py
  Rule: The kernel's side

    Scenario: A move into a paragraph a colleague is writing in is refused
      When an object is moved into a paragraph that another person holds
      Then the move is refused as locked, and the object stays where it was

    Scenario: Undo puts the object back at its place in the stacking order of its old paragraph
      Given two objects hang from the first paragraph, the moved one behind the other
      When it is moved to the third paragraph and the move is undone
      Then it is behind the other again
