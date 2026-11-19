# What a document needs from the server it is opened on (E1.9, D1306, D1313)
Feature: A document opened on a server that lacks or changed something it needs says so precisely and still opens

  @core @needs-decision @pending:e1.9
  Scenario: A workbook calls a function this server does not have
    Given a workbook whose cells use TAXRATE, made on another server
    When I open it here
    Then it opens, and the cells show #NAME? and keep their formulas
    And a banner says "TAXRATE is not installed on this server (used in 14 cells)"

  @core @needs-decision @pending:e1.9
  Scenario: A function has changed since the workbook last used it
    Given a workbook last calculated with TAXRATE as it was on another server
    When I open it here, where TAXRATE is different
    Then the cells show the results of this server's TAXRATE
    And a banner says that TAXRATE has changed and results may differ
    When I am an editor and choose "Keep this version"
    Then the banner is gone and stays gone the next time I open the workbook

  @extended @needs-decision @pending:e1.9
  Scenario: A viewer is told but cannot keep the new version
    Given the same changed function
    When a viewer opens the workbook
    Then she sees the banner and no "Keep this version"

  @core @needs-decision @pending:e1.9 @app:composes @app:computes @app:creates
  Scenario: A font the server lacks but can fetch is offered, and never blocks
    Given a document that uses a font this server does not have but can provide
    When I open it
    Then it opens, and a banner offers to get the font with one click

  @extended @needs-decision @pending:e1.9
  Scenario: The list of documents never shows what a document needs
    Given a workbook that uses a function called BONUS_BANDS
    When someone who may list the server looks at the list of documents
    Then the name BONUS_BANDS is nowhere in what they can read without the password
