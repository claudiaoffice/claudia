# Menus show what fits the moment; what does not fit says why (E5.23, E5.24; D1600–D1607, D1612, D1615, D1619,
# D1640–D1648). Questions and proposals: menus-that-fit.review.md.
@draft
Feature: The menus offer what fits who I am and what I am doing, and what does not fit tells me why

  # -- the menu bar --------------------------------------------------------------------------------------
  @core @firefox @desktop @pending:e5.24
  Scenario Outline: The menu titles stay, whoever I am
    Given I am <role> of a document
    Then the menu bar shows File, Edit, Insert, Format, View, Tools, Preferences and Help

    Examples:
      | role        |
      | the owner   |
      | an editor   |
      | a viewer    |

  @core @firefox @desktop @pending:e5.24 @app:computes
  Scenario: A viewer's Insert menu says why it is empty
    Given I am a viewer of a sheet
    When I open the Insert menu
    Then it holds only the greyed line "Nothing to insert: you can only look at this document."

  @core @firefox @pending:e5.23 @app:computes
  Scenario: The owner finds everything she can add under Insert, and none of it under Edit
    Given I am the owner of a sheet
    When I open the Insert menu
    Then it shows Image…, Text Box, Shape, Container and Chart…, then New Sheet… and Row or Column
    And the Edit menu holds nothing that adds something to the sheet

  @core @firefox @pending:e5.24 @app:composes
  Scenario: Edit offers what needs a selection only once something is selected
    Given I am the owner of a new text with nothing selected
    When I open the Edit menu
    Then it shows neither Copy, Cut nor Name & Describe…
    When I select a word and open the Edit menu again
    Then it shows Copy, Cut and Name & Describe…

  @extended @pending:e5.24 @app:composes
  Scenario: Undo appears once there is something to undo
    Given I am the owner of a new text
    Then the Edit menu shows no Undo
    When I type a word
    Then the Edit menu shows Undo

  @extended @pending:e5.24
  Scenario: No menu starts or ends with a line, and no two lines follow each other
    Given I am a viewer of a document
    Then in every menu and submenu no separator comes first, last or right after another

  @extended @two-users @pending:e5.24 @app:computes
  Scenario: A menu that is open does not change under my hand
    Given I am the owner of a sheet without a pivot table, and Ben is an editor of it
    And I have the Tools menu open
    When Ben adds a pivot table
    Then my open Tools menu stays as it was
    When I close it and open it again
    Then it is the same menu, and the pivot table's own entries are in its context menu

  # -- context menus -------------------------------------------------------------------------------------
  @core @firefox @pending:e5.24 @app:creates
  Scenario: A viewer's context menu on an object says why it is empty
    Given I am a viewer of a presentation with a text box
    When I press the right button on the text box
    Then the menu holds only the greyed line "You can only look at this document."

  @core @firefox @pending:e5.24 @app:composes
  Scenario: A paragraph has a context menu of its own
    Given I am the owner of a text
    When I press the right button on a paragraph
    Then the menu shows Name & Describe…, Style… and Reference in Chat
    When I choose Style…
    Then the paragraph style popover opens for that paragraph

  @core @firefox @pending:e5.24 @app:computes
  Scenario: A pivot table's actions are in its context menu
    Given I am the owner of a sheet with a pivot table
    When I press the right button on the pivot table
    Then the menu shows Value Field Settings…, Pivot Fields, Show Pivot as SQL… and Delete Pivot Table…
    And the Tools menu has the single entry Pivot Table…

  @extended @pending:e5.24 @app:creates
  Scenario: A slide has a context menu of its own
    Given I am the owner of a presentation
    When I press the right button on the slide, away from any object
    Then the menu shows Name & Describe… and Reference in Chat, the same as the slide's tab

  # -- a key that does not fit ---------------------------------------------------------------------------
  @core @firefox @pending:e5.24 @app:composes
  Scenario: The key of an entry I am not offered tells me why
    Given I am a viewer of a text
    When I press Ctrl+Shift+Alt+S
    Then I am told "Only an owner can share this document."
    And no dialog opens

  @extended @pending:e5.24 @app:computes
  Scenario: When several things are missing, I am told about who I am first
    Given I am a viewer of a sheet with nothing selected
    When I press Ctrl+Alt+D
    Then I am told "You can only look at this document.", not that nothing is selected

  @extended @pending:e5.24 @app:composes
  Scenario: The key of an entry the server cannot do tells me so
    Given I am the owner of a text on a server without a real ai
    When I press Ctrl+F1
    Then I am told "The ai is not set up on this server."

  # -- copying and pasting -------------------------------------------------------------------------------
  @core @firefox @pending:e5.24 @app:composes
  Scenario: A viewer cannot copy from the document
    Given I am a viewer of a text, and the clipboard holds the words "kept before"
    When I select a sentence and press Ctrl+C
    Then I am told "Only editors and owners can copy from this document."
    And the clipboard still holds "kept before"

  @extended @pending:e5.24 @app:composes
  Scenario: A viewer cannot copy through the browser's own menu or by dragging
    Given I am a viewer of a text, and the clipboard holds the words "kept before"
    When I select a sentence and choose Copy in the browser's own menu
    Then the clipboard still holds "kept before"
    When I drag the sentence into a text field outside the document
    Then nothing arrives there

  @extended @pending:e5.24 @app:composes
  Scenario: A viewer cannot copy the ai's answer that quotes the document
    Given I am a viewer of a text, and the ai has answered my question with a sentence of the text
    When I select the answer in History & Chat and press Ctrl+C
    Then I am told "Only editors and owners can copy from this document."

  @extended @pending:e5.24 @app:composes
  Scenario: A viewer can still download, export and print
    Given I am a viewer of a text
    Then the File menu offers Download, Export… and Print…

  @extended @pending:e5.24 @app:composes
  Scenario: Paste As Plain Text with a picture on the clipboard says there is no text
    Given I am the owner of a text, and the clipboard holds a picture
    When I choose Edit ▸ Paste As ▸ Plain Text
    Then I am told "There is no text to paste."
    And the text is unchanged

  # -- Preferences ▸ Shortcuts ---------------------------------------------------------------------------
  @core @firefox @pending:e5.24 @app:composes
  Scenario: The Shortcuts dialog lists every action, also those that do not fit now
    Given I am a viewer of a text
    When I choose Preferences ▸ Shortcuts and switch to Everything
    Then Share… is listed with Ctrl+Shift+Alt+S, "owners" and the tag "not for you"
    When I switch to What Fits Now
    Then Share… is not listed

  # -- the trial -----------------------------------------------------------------------------------------
  @core @firefox @pending:e5.24 @app:computes
  Scenario: With "role" set to grey, a viewer sees the entries greyed
    Given the trial setting greys what does not fit my role
    And I am a viewer of a sheet
    When I open the Insert menu
    Then it shows all its entries, greyed

  @extended @pending:e5.24 @app:composes
  Scenario: An entry set to always show stays when its reason hides
    Given the trial setting always shows Undo
    And I am the owner of a new text
    Then the Edit menu shows Undo, greyed

  # -- in my language ------------------------------------------------------------------------------------
  @extended @pending:e5.24 @app:computes
  Scenario: What says why is in my own language
    Given I have chosen German as the app language
    And I am a viewer of a sheet
    When I open the Insert menu and press Ctrl+Shift+Alt+S
    Then the greyed line and the notice are in German
