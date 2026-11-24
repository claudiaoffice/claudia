# A refusal of a document reaches a person in her language (CODE-78, D1510).
#
# "I work in German" is a person who chose German for the interface: the page and what the server says are German.
# A refusal is what the document says when it will not do what was asked (a name that another thing has, a table that
# cannot be sorted). Refusals that only a wrong client could cause (a malformed request) stay in English: no person
# meets them.
#
# Approved by the owner on 2026-11-23: typed refusals, for the refusals a person can meet.
Feature: A document refuses in the language of the person who asked

  @core @app:computes
  Scenario: A sheet cannot take the name of another sheet, said in German
    Given a workbook with the sheets "Plan" and "Costs"
    And I work in German
    When I rename the sheet "Plan" to "Costs"
    Then I am told "Es gibt schon ein Tabellenblatt namens „Costs“"
    And the sheets are still called "Plan" and "Costs"

  @extended @app:creates
  Scenario: A slide cannot take the name of another slide, said in German
    Given a presentation with the slides "Start" and "End"
    And I work in German
    When I rename the slide "Start" to "End"
    Then I am told "Es gibt schon eine Folie namens „End“"
    And the slides are still called "Start" and "End"

  @extended @unit:tests/test_extract_i18n.py @unit:tests/test_catalogs.py
  Scenario: Every refusal a person can meet has its German words
    Given the refusals of the core and of the three apps
    Then each has a German translation whose blanks are the same as the English ones
