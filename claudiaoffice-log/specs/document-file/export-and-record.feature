# What leaves the document is exported on purpose and recorded (D1270, D1271, D1272, E2.9)
Feature: An unencrypted export asks first, is recorded, and comes back in as a new document

  Background:
    Given a new composes document "plan" in which I am Ann, an owner
    And the text has the paragraph "First line"

  @core @app:composes
  Scenario: Ann exports the document without protection after being told what that means
    When I choose File ▸ Manage ▸ Export… and the format "Claudia, unencrypted (JSON in a zip)"
    And I press Export
    Then I am asked "Save without protection?" and told that anyone who gets the file can read it
    When I press Export unprotected
    Then a file ending in ".claudia-export.zip" is saved
    And the file is a zip with a readable "content.json" that holds "First line"
    And the file has no key slots, no list of people and no password hashes
    And the History & Chat panel has the muted line "exported unprotected · content"

  @core @app:composes
  Scenario: Ann changes her mind at the question and nothing is saved or recorded
    When I choose File ▸ Manage ▸ Export… and the format "Claudia, unencrypted (JSON in a zip)"
    And I press Export
    And I press Cancel at the question
    Then no file is saved
    And the History & Chat panel has no muted line about an export

  @core @app:composes
  Scenario: An owner adds the history and the chat, and the record says all parts
    When I choose File ▸ Manage ▸ Export… and the format "Claudia, unencrypted (JSON in a zip)"
    And I tick "Include history and chat"
    And I press Export
    And I press Export unprotected
    Then the file holds a "history.jsonl" and a "chat.jsonl"
    And the History & Chat panel has the muted line "exported unprotected · all parts"

  @core @app:composes @two-users
  Scenario: An editor may export the content and is told that the history is for owners
    Given Ben is an editor of the document
    When Ben opens the document
    And Ben chooses File ▸ Manage ▸ Export… and the format "Claudia, unencrypted (JSON in a zip)"
    Then Ben sees no box to include history and chat
    And Ben is told that history and chat can only be exported by owners

  @core @app:composes
  Scenario: A PDF saved from the print preview is recorded with its pages
    When I choose File ▸ Print… and press Download PDF
    Then the History & Chat panel has a muted line beginning "saved a PDF · "

  @core @app:composes
  Scenario: The unencrypted export comes back in as a new document with the same text
    Given I exported the document without protection
    When I give that file to the Open page
    Then the dialog says "A Claudia export, made by ann"
    And the dialog has no box to keep the original
    When I name the new document "plan-again" and give a password and press Open
    Then the new document has the paragraph "First line"
    And I am its only owner

  @extended @io:packages/claudia-server/tests/test_server_export_import.py
  Scenario: An owner's export comes back in with the history of the original as one note
    Given Ann changed the document and wrote "A1 is the budget" in the chat for everybody and one private message
    And Ann exported the document without protection with its history and chat
    When Nora makes a new document of that file
    Then the dialog said that the people named in its history are not given access
    And the new document's history has one step, the import, with a folded "History of the original"
    And the note names Ann for her change and for "A1 is the budget", with when, and not the private message
    And Nora has nothing to undo

  @extended @unit:packages/claudia-document-file/tests/test_audit.py
  Scenario: A redaction, a restore and a packing do not change one byte of the record
    Given the document has two entries in its record
    When an owner redacts a change, the document is packed and the history is rewritten
    Then the blocks of the record are byte for byte the ones from before

  @extended @unit:packages/claudia-server/tests/test_server_audit.py
  Scenario: A viewer's export or print is recorded under her own name and she cannot read the record
    Given Vera is a viewer
    When she exports the content, prints and saves a PDF
    Then the record names her for each, whatever her window says
    And asking for the record is refused to her
    And at most twenty prints and PDFs a minute are taken from one person

  @extended @unit:packages/claudia-document-file/tests/test_export_file.py
  Scenario: A file that is not an export, is changed, or is a bomb is refused with a sentence
    Then a part that does not fit export.json, a newer version, a path in a name and a bomb are each refused
