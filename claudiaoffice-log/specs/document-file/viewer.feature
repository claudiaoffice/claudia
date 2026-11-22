# A viewer reads the document and is not shown how it came to be (D1261, D1262, E2.11)
Feature: A viewer sees the content, and nothing of the history or the chat

  Background:
    Given a new composes document "plan" in which I am Ann, an owner
    And the text has the paragraph "First line"
    And Vera is a viewer of the document

  @core @app:composes @two-users
  Scenario: Vera sees the text and is told that history and chat are for editors
    When Vera opens the document
    Then Vera sees the paragraph "First line"
    And Vera's side panel says that history and chat are for the document's editors
    And Vera's side panel lists no history

  @core @app:composes @two-users
  Scenario: What Ann writes next appears for Vera and the history stays closed to her
    Given Vera has the document open
    When Ann adds the paragraph "Second line"
    Then Vera sees the paragraph "Second line"
    And Vera's side panel lists no history

  @core @app:composes @two-users
  Scenario: Vera opens a document nobody has open and waits until an editor opens it
    Given the server was restarted and nobody has opened the document since
    When Vera opens the document
    Then Vera is told that an editor or owner has to open it first
    And Vera's window does not give up
    When Ann opens the document again
    Then Vera's window opens it by itself and shows "First line"

  # The refusals of the server are checked by the unit tests of the protocol, which can ask for what a window would not.
  @extended @unit:packages/claudia-server/tests/test_server_audience.py
  Scenario: A viewer who asks for the history, the chat or a checkpoint over the wire is refused
    Given Vera is connected as a viewer
    When she asks for the log, the history, the chat, the checkpoints or an older revision
    Then each request is refused with the reason that these are for editors and owners
    And nothing from the history, the chat or a checkpoint is pushed to her while Ann works

  @extended @unit:packages/claudia-server/tests/test_server_audience.py
  Scenario: Every method of the protocol says which part of the document it reads
    Then a method that reads the history or the chat is refused to a viewer
    And a new method is a content method unless it says otherwise, and the list of the others is reviewed
