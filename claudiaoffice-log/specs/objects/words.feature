# Writing in a text box or a shape (D1232)
@e2e:objects.cjs
Feature: The words of a text box and of a shape are written the same way in every app that has them

  @core @app:composes @app:creates
  Scenario: Edit text from the object's menu
    Given a text box (or a shape) is on the page
    When I press the right button on it and choose "Edit text"
    And I type "words by ann" and press Enter
    Then the words are on the object, as one entry "Edit text" in the history
    And the second person in the document sees the same words

  @core @app:composes @app:creates
  Scenario: Enter, F2 and a double press open the editor; Esc leaves the words as they were
    Given a text box is selected
    When I press Enter and type " not kept" and press Esc
    Then nothing is added to the history and the words are as they were
    And a double press on the box opens the editor again

  @extended @app:composes @app:creates
  Scenario: The words that stay keep their writer
    Given ann wrote "Why we did it" in a box
    When ben changes it to "Why we really did it"
    Then only the changed words are ben's, and Undo takes back exactly his change

  @core @app:computes @app:composes @app:creates
  Scenario: A picture and a chart have no Edit text; a container is written in its own editor
    Given a picture is selected
    Then its menu has no "Edit text"
    When a container is selected and I choose "Edit text"
    Then its definition opens in the container editor

  @unit:packages/claudia-server/tests/test_server_object_words_and_turns.py
  Scenario: composes' server takes `write_words` and `set_text`
    Given a text with a text box in it
    When the words are written as typed
    Then the server changes only what differs, and writes nothing for the same words
