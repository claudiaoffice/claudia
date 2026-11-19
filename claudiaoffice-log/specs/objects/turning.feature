# Turning an object in every app (D1021, D1024, D1224, D1232)
@e2e:objects.cjs
Feature: Every app that has floating objects turns them the same way, and a chart and a table never turn

  @core
  Scenario: Format ▸ Rotate turns the selected object by a quarter each way
    Given a text box, a shape or a picture is selected
    When I choose Format ▸ Rotate ▸ Rotate Right 90°, or press Ctrl+Alt+.
    Then it is turned a quarter clockwise, as one entry in the history
    And Rotate Left 90° (Ctrl+Alt+,) turns it back

  @core
  Scenario: Rotate By… asks for any angle
    Given an object is selected
    When I choose Format ▸ Rotate ▸ Rotate By… (Ctrl+Shift+Alt+Z) and give 45
    Then the object is turned to 45° in one entry, and I hear "Turned to 45°"
    And leaving the popover with Esc changes nothing

  @core
  Scenario: Nothing to turn
    Given nothing is selected, or a chart, or a table, or the document is read-only
    Then the three Rotate entries are off, the object's menu has no Rotate by…, and no turn handle is drawn

  @extended
  Scenario: The object's menu says the key
    Given an object that turns is selected
    When I press the right button on it
    Then "Rotate by…" shows Ctrl+Shift+Alt+Z beside it, as the menu bar does

  @unit:packages/claudia-server/tests/test_server_object_words_and_turns.py
  Scenario: The server refuses a table and a chart, and reads angles modulo a turn
    When `rotate_object` is called for a table or a chart
    Then it answers "A table does not turn" or "A chart does not turn", and nothing changes
    And −20° is stored as 340°

  @unit:clients/linux/tests/test_manifest.py
  Scenario: The three apps' menus (web, GTK, Neutralino) carry the same entries and keys
    Given the manifest
    Then composes, computes and creates each have Format ▸ Rotate ▸ with the same three entries and keys
