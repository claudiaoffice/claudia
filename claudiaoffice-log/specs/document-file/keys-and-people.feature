# People have keys of their own; lowering a role or removing somebody renews the keys (D1263, D1264, D1265, D1274, E2.3)
Feature: An owner lowers a role or removes a person, and the document's keys are renewed

  Background:
    Given a new composes document "plan" in which I am Ann, an owner
    And the text has the paragraph "First line"
    And Ben is an editor of the document

  @core @app:composes
  Scenario: Ann sees everybody in the document with a role each
    When I choose File ▸ Manage ▸ Share…
    Then the dialog lists "ann" as "owner"
    And the dialog lists "ben" as "edit"
    And only Ben has a way to be removed

  @core @app:composes @two-users
  Scenario: Ann lowers Ben to "only look" after being told what that protects
    Given Ben has the document open
    When I choose File ▸ Manage ▸ Share… and change what ben may do to "only look"
    Then I am asked "Change ben to “only look”?" and told that ben cannot read what is written from now on
    When I press Change to only look
    Then the dialog lists "ben" as "only look"
    And Ben's window says "Your role in this document is now “only look”."
    And Ben's side panel says that history and chat are for the document's editors

  @core @app:composes
  Scenario: Ann changes her mind at the question and nothing changes
    When I choose File ▸ Manage ▸ Share… and change what ben may do to "only look"
    And I press Cancel at the question
    Then the dialog lists "ben" as "edit"

  @core @app:composes @two-users
  Scenario: Ann removes Ben, and Ben is out at once
    Given Ben has the document open
    When I choose File ▸ Manage ▸ Share… and press Remove for ben
    Then I am asked "Remove ben from “plan”?" and told that private notes of this person are deleted
    When I press Remove ben
    Then the dialog does not list "ben" any more
    And Ben's window says "You are no longer a person of this document."
    And Ben cannot open the document with his password

  @core @app:composes @two-users
  Scenario: Ann carries on after the renewal and the text is still there
    Given Ben has the document open
    When Ann removes Ben
    Then Ann's window shows the paragraph "First line"
    And Ann can keep typing and the paragraph she types is saved

  @core @app:composes @two-users
  Scenario: An editor cannot open the Share dialog
    When Ben opens the document
    Then Ben's File ▸ Manage ▸ Share… entry cannot be chosen

  @extended @unit:packages/claudia-document-file/tests/test_renewal.py
  Scenario: Removing a viewer renews the content key; removing an editor renews all keys

  @extended @unit:packages/claudia-document-file/tests/test_renewal.py
  Scenario: Lowering an editor renews the history and chat keys and leaves the content key alone

  @extended @unit:packages/claudia-document-file/tests/test_renewal.py
  Scenario: A renewal that is interrupted after the file was written hands back the new keys

  @extended @unit:packages/claudia-document-file/tests/test_inbox.py
  Scenario: A person who was away gets the new keys with her next login, and a forged letter is ignored

  @extended @unit:packages/claudia-document-file/tests/test_private_notes.py
  Scenario: A person's private notes open with her private key only, and recovery gives her fresh ones

  @extended @unit:packages/claudia-server/tests/test_server_people_changes.py
  Scenario: Only owners change roles; owners cannot be lowered or removed; a removed person's requests are refused
