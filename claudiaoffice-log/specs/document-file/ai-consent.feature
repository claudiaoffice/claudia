# The owners' consent: a document's owners decide whether Claude may receive its content (E7.11, D264)
# Mock-up: notes/mockups/ai-provider-3-owners-consent.svg (also a page of penpot/claudia.penpot).
# Architecture: notes/e7-11-architecture.md §3.4. The consent is kept in the document, sealed with its keys, in a list of its
# own beside the exit record; it is not part of the history, the chat or the exit record.
#
# "Allowed" always means: the owners' consent for the one remote provider the dialog names, "Claude (Anthropic)". Where the
# fake Anthropic is mentioned it stands in for Anthropic (see server/claude-as-ai-provider.feature).
# Decided on 2026-11-22: a copy of a document carries its consent to another server (no record of which server gave it);
# where that server has no Claude, nothing is an error: the server's own AI provider answers and the chat says who did.
# Provisional chord (2026-11-22): the owner asked for Ctrl+Shift+Alt+H, but that is Present from This Slide; E was free in all
# three apps. The owner decides; see the decision log of E7.11.
Feature: Only a document's owners can allow Claude to receive its content, and everybody can see whether they did

  As an owner of a document, I want Claude to see my document only if I say so, so that setting up Claude on the server
  does not send my content anywhere by itself.

  Background:
    Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
    And a new computes document "budget" in which I am Anna, an owner
    And the sheet "Budget" has the numbers 1 to 8 in column A

  # --- the menu entry -----------------------------------------------------------------------------------------------

  @core @desktop
  Scenario: The menu is called Preferences and has AI… with its key
    When I open the Preferences menu
    Then it has the entries "App language", "Shortcuts" and "AI…"
    And "AI…" shows the key "Ctrl+Shift+Alt+E"
    And no menu is called "Config"

  @core
  Scenario Outline: The same entry and key in all three apps
    Given a new <document> "plan" in which I am Anna, an owner
    When I press Ctrl+Shift+Alt+E
    Then the dialog "AI in this document" opens

    Examples:
      | document     |
      | workbook     |
      | text         |
      | presentation |

  @core
  Scenario: The dialog opens from the menu and closes with Escape without changing anything
    When I open the Preferences menu and choose "AI…"
    Then the dialog "AI in this document" opens with the focus in it
    When I press Escape
    Then the dialog is closed
    And Claude is still not allowed in "budget"

  # --- off by default -----------------------------------------------------------------------------------------------

  @core
  Scenario: Claude is not allowed in a new document
    When I open the dialog "AI in this document"
    Then the box "Allow Claude to answer @ai in this document" is not ticked
    And I read "Off by default. Only the owners can change it."
    And I read what Anthropic is sent if I allow it
    And what answers @ai in this document now is the server's local provider, with no "remote" badge

  @core
  Scenario: The dialog lists exactly what Claude is sent
    When I open the dialog "AI in this document"
    Then I read "the question, and the earlier chat between the person who asks and the ai"
    And I read "the parts of this document the ai looks at to answer her"
    And I read "Documents are encrypted on this server. Claude reads what it is shown in plain text."

  # --- allowing and withdrawing -------------------------------------------------------------------------------------

  @core
  Scenario: An owner allows Claude
    When I open the dialog "AI in this document"
    And I tick "Allow Claude to answer @ai in this document" and press Save
    Then the History & Chat panel names "Claude" with a "remote" badge on the ai's row
    When I open the dialog "AI in this document" again
    Then the box is ticked
    And I read "Allowed by Anna" and today's time and "for Claude (Anthropic)"
    And I read "Switching it off stops a question that is running before its next step."

  @core
  Scenario: An owner withdraws the consent
    Given Anna allowed Claude in "budget"
    When I open the dialog "AI in this document"
    And I untick "Allow Claude to answer @ai in this document" and press Save
    Then the ai's row names the local provider, with no "remote" badge
    And Claude is not allowed in "budget"

  @core
  Scenario: Cancel changes nothing
    When I open the dialog "AI in this document"
    And I tick "Allow Claude to answer @ai in this document" and press Cancel
    Then Claude is not allowed in "budget"

  @core
  Scenario: The dialog can be saved with the keyboard
    When I open the dialog "AI in this document"
    And I tick "Allow Claude to answer @ai in this document" and press Enter
    Then Claude is allowed in "budget"

  @core
  Scenario: The consent is still there after the document is closed and opened again
    Given Anna allowed Claude in "budget"
    When I close the document and open it again
    Then Claude is allowed in "budget"
    And I read "Allowed by Anna" in the dialog

  @core
  Scenario: The consent is still there after the server is restarted
    Given Anna allowed Claude in "budget"
    When the server is restarted
    And I open "budget"
    Then Claude is allowed in "budget"

  # --- who may change it, who can see it ----------------------------------------------------------------------------

  @core @two-users
  Scenario: An editor sees what is allowed and cannot change it
    Given Jonas is an owner and Ben is an editor of "budget"
    And Anna allowed Claude in "budget"
    When Ben opens the dialog "AI in this document"
    Then Ben reads "Allowed by Anna" and "for Claude (Anthropic)"
    And Ben reads "Only the owners can change this: Anna and Jonas."
    And the box is not available to Ben
    And Ben has no "Save" button, only "Close"

  @core @two-users
  Scenario: A viewer can see it too
    Given Vera is a viewer of "budget"
    And Anna allowed Claude in "budget"
    When Vera opens the dialog "AI in this document"
    Then Vera reads that Claude is allowed, by whom and when
    And Vera reads what Claude is sent when someone asks @ai
    And Vera cannot change it

  @core @two-users
  Scenario: Everybody in the document sees the change at once
    Given Ben is an editor of "budget" and has it open
    When Anna allows Claude in "budget"
    Then Ben sees "Claude" with a "remote" badge on the ai's row without reloading
    When Anna withdraws it
    Then Ben sees the local provider on the ai's row without reloading

  @extended @two-users
  Scenario: An editor who tries to change it anyway is refused and nothing changes
    Given Ben is an editor of "budget"
    When Ben's window sends the request to allow Claude
    Then Ben is told that only owners can change this
    And Claude is not allowed in "budget"

  @extended @two-users
  Scenario: Ownership handed over takes the right to change it with it
    Given Jonas is an editor of "budget"
    When Anna hands the ownership of "budget" over to Jonas and Jonas accepts
    Then Jonas can change the consent
    And Anna, now an editor, can only look at it

  # --- the administrator is not the owners --------------------------------------------------------------------------

  @core
  Scenario: The administrator cannot allow Claude in a document
    Given I am the administrator "anna" of the server as well as the owner of "budget"
    When I open the server settings
    Then there is no switch for "budget" anywhere in them

  @extended
  Scenario: Whoever edits the server's own files cannot allow Claude in a document either
    When the server's settings and state folder are changed to say that Claude is allowed in "budget"
    And the server is restarted
    Then Claude is still not allowed in "budget"

  @extended
  Scenario: The administrator's approval alone has not allowed anything
    Given the administrator has applied Claude
    Then in a document that Anna made today the box "Allow Claude to answer @ai in this document" is not ticked

  # --- where it is kept ---------------------------------------------------------------------------------------------

  @extended
  Scenario: Allowing Claude is not an export and is not in the exit record
    Given Anna allowed Claude in "budget"
    When I look at the exit record of "budget"
    Then it has no row for it

  @extended
  Scenario: Allowing Claude is not a step of the history
    Given Anna allowed Claude in "budget"
    Then the history of "budget" has no step for it
    And undoing and redoing does not change whether Claude is allowed

  @needs-decision
  Scenario: Everybody in the document is told when the consent changes, in the History & Chat panel
    When I allow Claude in "budget"
    Then the History & Chat panel has the muted line "Anna allowed Claude to answer @ai (remote)"
    When I withdraw it
    Then the panel has the muted line "Anna withdrew Claude's permission to answer @ai"

  # --- documents on other servers, and documents from before --------------------------------------------------------

  @extended
  Scenario: A copy of the document carries its consent to a server that has Claude
    Given Anna allowed Claude in "budget"
    And a second server whose AI provider is Claude, with the sentence confirmed
    When I keep a sealed copy of "budget" and put it on the second server
    And I open it there as Anna
    Then I read "Allowed by Anna" in the dialog
    And what answers @ai is Claude, with a "remote" badge

  @extended
  Scenario: A copy that comes to a server without Claude is not an error and says who answers
    Given Anna allowed Claude in "budget"
    And a second server whose AI provider is its local model
    When I keep a sealed copy of "budget" and put it on the second server
    And I open it there as Anna
    Then the dialog says "This server has no remote AI, so nothing in this document leaves it."
    And I read "An administrator can add Claude in the server settings."
    When I ask @ai a question
    Then the answer comes from the local model, with no error line
    And under it I read "answered by" and the local model

  @extended
  Scenario: Removing Claude from the server and adding it again keeps the owners' consent
    Given Anna allowed Claude in "budget"
    When the administrator removes the provider key and chooses the local model
    And later chooses Claude again with a key and the confirmed sentence
    Then Claude is allowed in "budget"

  @extended
  Scenario: A document made before this feature opens with Claude not allowed
    Given a document file made before the owners' consent existed
    When I open it
    Then it opens and Claude is not allowed in it
    And allowing Claude then works as in any other document

  @extended
  Scenario: A document that has an owners' consent is refused by a server that does not know it, in its usual words
    Given a document file in which Claude is allowed
    When a server of the version before this feature opens it
    Then the server says that the file is from a newer version of claudia
    And the document is not damaged

  # --- being usable by everybody ------------------------------------------------------------------------------------

  @extended
  Scenario: The dialog is usable with the keyboard and says its state in words
    When I open the dialog "AI in this document" with Ctrl+Shift+Alt+E
    Then the focus is in the dialog and Tab reaches every control in a sensible order
    And whether Claude is allowed is told in words, not by the tick alone
    And a screen reader reads the box with its label and whether it is ticked
    When I press Escape
    Then the focus is back where it was in the document

  @extended
  Scenario: The menu and the dialog are in my language
    Given my language is German
    When I open the Preferences menu
    Then every entry is German, "AI…" included, and its key is shown
    When I open the dialog
    Then every label, sentence and button is German
