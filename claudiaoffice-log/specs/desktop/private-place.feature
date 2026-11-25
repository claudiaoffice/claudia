# Private on this computer: a person's apps use only her own server (E8.5, CODE-99, CODE-100; D1620-D1623 proposed).
#
# Approved by the owner on 2026-11-25 (his answers are in the scenarios and in D1620-D1623). The desktop clients of all three systems: the macOS and Windows app
# (Neutralino) and the Linux app (GTK); the place names also in a plain browser tab. Two people on one computer are two
# accounts, each with her own folders; the tests stand them in as two homes on one test machine, so that the rules are
# checked without logging two people in. Which test checks a scenario is said by its tags; the browser tab's scenario is
# run by tests/e2e/specs/test_private_place.py.
Feature: Each person of a computer keeps her own private place

  @core @unit:clients/neutralino/tests/private-server.test.ts @unit:clients/linux/tests/test_private_server.py
  Scenario: My three apps share my private place
    Given I made "Notes" in claudia composes
    When I open claudia computes
    Then the first place in its list is "Private on this computer"
    And "Notes" is in that place

  # CODE-99
  @core @unit:clients/neutralino/tests/private-server.test.ts @unit:clients/linux/tests/test_private_server.py
  Scenario: Two people on one computer do not see each other's documents
    Given Anna and Ben each have an account on the same computer
    And Anna made "Anna's letter" and her claudia composes is still open
    When Ben opens claudia composes in his own account
    Then "Anna's letter" is not in Ben's "Private on this computer"
    And a document Ben makes there is not in Anna's "Private on this computer"

  # CODE-99
  @core @unit:clients/neutralino/tests/private-server.test.ts @unit:clients/linux/tests/test_private_server.py
  Scenario: My documents are still mine after the other person has logged out
    Given Ben made "Ben's notes" while Anna's apps were open
    When Anna logs out
    And Ben opens claudia computes again
    Then "Ben's notes" is in Ben's "Private on this computer"

  # CODE-100
  @core @unit:clients/neutralino/tests/private-server.test.ts @unit:clients/linux/tests/test_private_server.py
  Scenario: A shared server of another version does not keep my apps from opening
    Given this computer runs a shared claudia server of another version
    When I open claudia creates
    Then its window opens on "Private on this computer"

  @extended @unit:clients/neutralino/tests/private-port.test.ts @unit:clients/linux/tests/test_private_port.py
  Scenario: My lists stay with my private place from one day to the next
    Given I opened "Notes" from "Private on this computer" yesterday and put it into my collection "Work"
    When I open claudia composes today
    Then "Notes" is in Mine
    And "Notes" is in my collection "Work"

  @extended @unit:clients/neutralino/tests/private-server.test.ts @unit:clients/linux/tests/test_private_server.py
  Scenario: A program that is not mine on my private place's address
    Given a program that is not my claudia server answers where my private place usually is
    When I open claudia composes
    Then its window opens on "Private on this computer"
    And my documents are there
    And the next time I open an app, it tries my private place's usual address again

  @extended @unit:clients/neutralino/tests/private-server.test.ts @unit:clients/linux/tests/test_private_server.py
  Scenario: My own server of an older version is still running after an update
    Given my own claudia server of an older version still runs
    When I open claudia composes
    Then I am told that it stops by itself within ten minutes after its last window has closed

  @core @unit:web/tests/server-bookmarks.test.ts
  Scenario: The place names in my language
    Given my app language is German
    When I open claudia composes
    Then the first place in its list is "Privat auf diesem Computer"

  @extended @unit:web/tests/server-bookmarks.test.ts
  Scenario: My private place keeps the name the app gives it
    When I look at "Private on this computer" in my list of places
    Then I cannot rename it

  @core @firefox
  Scenario: A claudia server on this computer, opened in a browser tab
    Given a claudia server runs on this computer
    When I open its address in a browser tab
    Then its place is called "Shared on this computer"
    And no place is called "This computer"
