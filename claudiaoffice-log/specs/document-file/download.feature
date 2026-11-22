# File ▸ Download: my own sealed copy of the document (D110, D1270, E2.12)
Feature: Downloading a document as a Claudia file keeps it protected and gives each person only their part

  Background:
    Given a new composes document "report" in which I am Ann, an owner
    And the text has the paragraph "First line"

  @core @app:composes
  Scenario: The owner downloads the whole document and it opens with her name and password
    When I choose File ▸ Download, type my password and press Download
    Then a file ending in ".claudia" is saved
    And the file opens with Ann's name and her password
    And "First line" cannot be read in the file without them

  @core @app:composes
  Scenario: A wrong password gives no file
    When I choose File ▸ Download, type a wrong password and press Download
    Then no file is saved
    And I am told that it is not my current password

  @core @app:composes
  Scenario: The dialog says what my file will hold
    When I choose File ▸ Download
    Then the dialog says the file has the history, the chat and the people, and is still protected
    And it says where to find Word, Excel and PowerPoint files instead

  @extended @app:composes @two-users
  Scenario: An editor's copy opens only with her own name and password
    Given Ben is an editor of the document
    When Ben downloads the document with his password
    Then the file opens with Ben's name and his password
    And the file does not open with Ann's name and password

  @extended @app:composes @two-users
  Scenario: A viewer's copy has the content and no history or chat
    Given Vera is a viewer of the document, and Ann has it open
    When Vera downloads the document with her password
    Then the file opens with Vera's name and her password
    And the file holds no history and no chat
    And the dialog told Vera it has none

  @extended @app:composes
  Scenario: The file can be taken in again, as the same document
    Given I have downloaded the document
    When I delete it from the server and open the file with Open ▸ Open file
    Then the document is there again with "First line" in it
