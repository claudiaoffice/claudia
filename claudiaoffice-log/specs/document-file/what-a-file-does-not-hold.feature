# After an export to another format, the Export dialog says what the file does not hold (UX-70, D405; the agreed design
# is panel B of notes/mockups/export-dialog-tracked-changes.svg)
@draft
Feature: The Export dialog says what a file in another format does not hold

  @core @app:composes
  Scenario: Ann is told that an OpenDocument text does not hold who typed which words
    Given a new composes document "plan" in which I am Ann, an owner
    And I have typed the paragraph "First line"
    When I choose File ▸ Manage ▸ Export… and the format "OpenDocument text (.odt)"
    And I press Export
    Then a file ending in ".odt" is saved
    And the dialog says "The file does not hold:" with the line "Who typed which words"
    And under it "This format has no place to keep it."
    And then "Everything else is in the file."

  @core @app:composes
  Scenario: Each kind of thing the file does not hold is said once, with how many
    Given a new composes document "plan" in which I am Ann, an owner
    And the text has two remarks and three open suggestions
    When I export it as "Word document (.docx)"
    Then the dialog says the line "Remarks are not in the file (2)" once
    And the line "Open suggestions are not in the file (3)" once
    And under it "Accept or reject them first to have the words you want in the file."

  @extended @app:computes
  Scenario: A kept file that could not be changed in place says so
    Given I opened an Excel file "budget.xlsx" in computes and kept the file
    And I have done something the file cannot take in place
    When I export it as "Excel workbook (.xlsx)"
    Then the dialog says the line "The file was written anew, not changed in place"
    And under it "So what this program does not show of the original is not in it."

  @extended @app:creates
  Scenario: A screen reader hears what the file does not hold
    Given a new creates presentation "pitch" in which I am Ann, an owner
    And a slide has a planned time of 2 minutes
    When I export it as "PowerPoint presentation (.pptx)"
    Then a screen reader announces "Planned times of slides" without my moving to it
