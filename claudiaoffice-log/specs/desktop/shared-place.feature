# Shared on this computer: the claudia service is a place of its own (E8.5; D1622, D1624 proposed; supersedes D743's
# "the apps use the service's documents").
#
# Approved by the owner on 2026-11-25 (his answers are in the scenarios and in D1622, D1624). macOS and Windows: the service is an option of their installers, off by
# default. The Linux package has no service (E8.5, Q21). As on any server, every person of the computer sees the titles of
# the shared documents that are not unlisted, and opens one only with a role. A new document's place is chosen in the
# Open/New dialog, as for any server. Which test checks a scenario is said by its tags; the others are run by
# tests/e2e/specs/test_shared_place.py, where a server on 127.0.0.1 stands in for the service.
Feature: The people of a computer share documents through its claudia service

  @core @unit:clients/neutralino/tests/core.test.ts @unit:clients/neutralino/tests/shared-service.test.ts
  Scenario: Every person of the computer finds the shared place
    Given the claudia service is installed on this computer
    When Anna opens claudia composes
    Then her places are "Private on this computer", then "Shared on this computer"
    And when Ben opens claudia composes in his own account, his places are the same two

  @core @unit:clients/neutralino/tests/core.test.ts @unit:clients/neutralino/tests/shared-service.test.ts
  Scenario: Without the service there is no shared place
    Given the claudia service is not installed on this computer
    When I open claudia composes
    Then no place is called "Shared on this computer"

  @core @unit:clients/neutralino/tests/core.test.ts
  Scenario: A new document goes to my private place unless I choose the shared one
    Given the claudia service is installed on this computer
    When I make a new document in claudia computes without choosing a place
    Then it is in "Private on this computer"
    And it is not in "Shared on this computer"

  @core @two-users
  Scenario: Two people of the computer work on one shared document
    Given the claudia service is installed on this computer
    And Anna made "Family budget" in "Shared on this computer" and gave Ben the role editor
    When Ben opens "Family budget" from "Shared on this computer" with his own password
    Then Ben can change it
    And Anna sees his change

  @extended
  Scenario: An administrator of the computer names the service's first administrator
    Given the claudia service has no administrator yet
    And I am an administrator of this computer
    When I open the settings of "Shared on this computer"
    Then its setup code is filled in for me
    And I can make myself its first administrator

  @extended
  Scenario: Anyone else is told whom to ask
    Given the claudia service has no administrator yet
    And I am not an administrator of this computer
    When I open the settings of "Shared on this computer"
    Then I read "Only an administrator of this computer can name this server's first administrator. Ask one."
    # German: "Nur ein Administrator dieses Computers kann den ersten Administrator dieses Servers bestimmen. Fragen Sie einen."

  @extended @unit:web/tests/server-bookmarks.test.ts
  Scenario: The shared place keeps its name once it has an administrator
    Given the claudia service's administrator is Anna
    When Ben opens claudia composes
    Then its second place is "Shared on this computer"

  # With a shared document open while the service is removed, the window says the connection is lost and keeps trying,
  # as when any server goes away.
  @extended @unit:clients/neutralino/tests/core.test.ts @unit:clients/neutralino/tests/shared-service.test.ts
  Scenario: The shared place disappears with the service
    Given the claudia service was installed and has been removed
    When I open claudia composes
    Then no place is called "Shared on this computer"
    And my documents in "Private on this computer" are there

  @extended @app:composes @unit:web/tests/server-bookmarks.test.ts
  Scenario: The shared place in my language
    Given the claudia service is installed on this computer
    And my app language is German
    When I open claudia composes
    Then its places are "Privat auf diesem Computer", then "Geteilt auf diesem Computer"

  @extended @unit:tests/test_windows_packaging.py
  Scenario: The Windows installer says what the service is for
    When I choose the components of Claudia Office on Windows
    Then the service is described as "Claudia server as a Windows service, for the people of this computer to share documents"
    And it is not chosen unless I choose it
