# Shared on this computer: the claudia service is a place of its own (E8.5; D1622, D1624 proposed; supersedes D743's
# "the apps use the service's documents").
#
# Draft for the owner's review (2026-11-25). macOS and Windows: the service is an option of their installers, off by
# default. The Linux package has no service (E8.5, Q21). Open edge cases, each with a proposed default:
# shared-place.review.md.
@draft
Feature: The people of a computer share documents through its claudia service

  @core
  Scenario: Every person of the computer finds the shared place
    Given the claudia service is installed on this computer
    When Anna opens claudia composes
    Then her places are "Private on this computer", then "Shared on this computer"
    And when Ben opens claudia composes in his own account, his places are the same two

  @core
  Scenario: Without the service there is no shared place
    Given the claudia service is not installed on this computer
    When I open claudia composes
    Then no place is called "Shared on this computer"

  @core
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

  @extended
  Scenario: The shared place disappears with the service
    Given the claudia service was installed and has been removed
    When I open claudia composes
    Then no place is called "Shared on this computer"
    And my documents in "Private on this computer" are there

  @extended @app:composes
  Scenario: The shared place in my language
    Given the claudia service is installed on this computer
    And my app language is German
    When I open claudia composes
    Then its places are "Privat auf diesem Computer", then "Geteilt auf diesem Computer"

  @extended
  Scenario: The Windows installer says what the service is for
    When I choose the components of Claudia Office on Windows
    Then the service is described as "Claudia server as a Windows service, for the people of this computer to share documents"
    And it is not chosen unless I choose it
