# The server's administrators: naming the first one, and what the settings pages promise about them (E3.11, SEC-12)
Feature: The administrator pages say only what the server really does

  # UX-61: both pages called the access secret a recovery key for administrators. It is not one: it lets people make
  # documents and read their list, and nobody can sign in with it.

  @core @unit:web/tests/admin-wording.test.ts
  Scenario: Naming the first administrator does not promise a way back that does not exist
    Given a server that has no administrator yet
    When I open its server settings
    Then the page does not call the access secret a recovery key
    And it says that only someone with access to the computer the server runs on can name a new first administrator

  @core @unit:web/tests/admin-wording.test.ts
  Scenario: The access secret is described as what it does
    Given I am signed in as an administrator
    When I open Access & documents
    Then the access secret is described as what lets people make documents and see their list
    And it is not called a recovery key
