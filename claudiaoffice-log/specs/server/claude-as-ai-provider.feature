# The administrator adds Claude as the server's AI provider (E7.11, D32, D264, D266, D154)
# Mock-ups: notes/mockups/ai-provider-1-server-settings.svg and ai-provider-2-settings-states.svg (also pages of
# penpot/claudia.penpot). Architecture: notes/e7-11-architecture.md.
#
# "Claude" is reached with a provider key, an API key of the administrator's Anthropic account. No scenario reaches the real
# Anthropic: "the fake Anthropic" is a small server on this computer that speaks the same API and can be told to refuse, to
# be out of credit, to be slow and so on; the server under test is started with its address (never settable from the page).
# One real-key check by the owner is the only run against the real API ("real API not run" is said in every patch).
# Words in the glossary: AI provider, Remote provider, Provider key, Owner's consent.
Feature: An administrator can make Claude the AI that answers @ai, and the page tells the truth about where content goes

  As the administrator of a server, I want to connect Claude in the server settings, so that @ai answers with Claude the
  way it answers with a local model, without anybody's content leaving the server unless the document's owner also agrees.

  Background:
    Given a server with the administrator "anna" and a fake Anthropic that accepts the provider key "sk-ant-test-a7Q2"
    And I am signed in to the server settings as "anna"

  # --- what answers now ---------------------------------------------------------------------------------------------

  @core
  Scenario: The AI page says in words what answers @ai now
    Given the server has no model folder
    When I open the AI page
    Then it says "Answering now:" and "Scripted stand-in"
    And it shows no "remote" badge
    And it says "Last error: none"

  @core
  Scenario: The page offers three AI providers and chooses the one that answers
    When I open the AI page
    Then I can choose between "Scripted stand-in", "Local model" and "Claude"
    And the chosen one is the one named after "Answering now:"

  @extended
  Scenario: A settings file from before Claude opens with the local model chosen
    Given the server was started with a saved model folder and no AI provider in its settings
    When I open the AI page
    Then "Local model" is chosen, with its folder, device, longest answer and timeout as they were

  # --- adding Claude ------------------------------------------------------------------------------------------------

  @core
  Scenario: Choosing Claude asks for the key and says where content goes
    When I open the AI page
    And I choose "Claude"
    Then I am asked to paste the key of my Anthropic account
    And the model is "claude-sonnet-5-5"
    And I read "Document content is sent to Anthropic when someone asks @ai."
    And I read "Documents are encrypted on this server; Claude reads what it is shown in plain text."
    And I read that the owner of each document must also allow Claude there
    And "Apply" is not available

  @core
  Scenario: Claude is applied with the right key once I have confirmed the sentence
    When I open the AI page
    And I choose "Claude"
    And I paste the key "sk-ant-test-a7Q2"
    And I confirm that document content is sent to Anthropic
    And I press Apply
    Then I read "Test answered"
    And it says "Answering now:" and "Claude · claude-sonnet-5-5" with a "remote" badge
    And I read "Confirmed by anna"
    And the fake Anthropic was asked one test question

  @core
  Scenario: The key is never shown again, only its last four characters
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    When I open the AI page
    Then the key reads "sk-ant-" followed by dots and "a7Q2"
    And I can press "Replace" or "Remove"
    And the page and the server's answers to it do not contain "sk-ant-test-a7Q2"

  @core
  Scenario: A key Anthropic refuses is refused here, with its reason, and nothing changes
    Given the server answers @ai with the local model
    When I open the AI page
    And I choose "Claude"
    And I paste the key "sk-ant-wrong-9ZkP"
    And I confirm that document content is sent to Anthropic
    And I press Apply
    Then I read "Anthropic refused the key."
    And I read "Nothing was changed"
    And it says "Answering now:" and the local model, with no "remote" badge
    And the fake Anthropic was asked one test question

  @extended
  Scenario Outline: Other things that go wrong at the test are refused with their reason
    Given the fake Anthropic <fails>
    When I open the AI page
    And I choose "Claude"
    And I paste the key "sk-ant-test-a7Q2"
    And I confirm that document content is sent to Anthropic
    And I press Apply
    Then I read "<reason>"
    And nothing was changed

    Examples:
      | fails                                | reason                                              |
      | refuses every key                    | Anthropic refused the key.                          |
      | says the credit balance is used up   | The credit balance at Anthropic is used up.         |
      | says the rate limit was reached      | Anthropic's rate limit was reached.                 |
      | says it is overloaded                | Anthropic is overloaded at the moment.              |
      | cannot be reached                    | Anthropic cannot be reached from this server.       |
      | does not know the model "claude-x"   | Anthropic does not know the model “claude-x”.       |

  @extended
  Scenario: Any model id may be typed
    When I open the AI page
    And I choose "Claude"
    And I type the model id "claude-opus-5-5"
    And I paste the key "sk-ant-test-a7Q2" and confirm the sentence and press Apply
    Then it says "Claude · claude-opus-5-5"
    And the fake Anthropic was asked for the model "claude-opus-5-5"

  # --- the two approvals --------------------------------------------------------------------------------------------

  @core
  Scenario: Applying Claude does not allow it in any document
    Given a document "budget" in which "jonas" is an owner
    When I apply Claude with the right key and the confirmed sentence
    Then the settings page has no switch for the document "budget"
    And in "budget" Claude is not allowed until its owner allows it

  @extended
  Scenario: The sentence is recorded with who confirmed it and when
    When I apply Claude with the right key and the confirmed sentence
    And I reload the AI page
    Then I read "Confirmed by anna" and today's date and time

  @extended
  Scenario: Changing the key does not ask for the sentence again, switching to Claude from another provider does
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    When I press "Replace" and paste the key "sk-ant-test-b4N8" and press Apply
    Then I am not asked to confirm the sentence again
    When I choose "Local model" and press Apply
    And I choose "Claude" and press Apply
    Then I am asked to confirm the sentence again

  # --- the provider key ---------------------------------------------------------------------------------------------

  @extended
  Scenario: A key given by the server's operator wins over the saved one
    Given the server's operator gave the key "sk-ant-test-b4N8" with the server's start
    And Claude is the server's AI provider with the saved key "sk-ant-test-a7Q2"
    When I open the AI page
    Then I read that the key is given by the server's operator
    And the fake Anthropic is asked with "sk-ant-test-b4N8" and never with "sk-ant-test-a7Q2"

  @extended
  Scenario: Removing the key leaves no key behind
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    When I press "Remove" and choose "Local model" and press Apply
    And I choose "Claude"
    Then I am asked to paste the key again
    And the server's settings file does not contain "sk-ant-test-a7Q2"

  @extended
  Scenario: The key is not in the server's log
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    When someone asks @ai in a document whose owner allowed Claude
    Then the server's log does not contain "sk-ant-test-a7Q2"

  @extended
  Scenario: Nobody but an administrator can open the AI page
    Given I am not signed in to the server settings
    When I open the AI page
    Then I am asked to sign in
    And the page shows no provider key and no setting of Claude

  # --- the local model is as it was ---------------------------------------------------------------------------------

  @extended
  Scenario: Choosing the local model shows its own settings, as before
    When I open the AI page
    And I choose "Local model"
    Then I see the model folder, the device, the longest answer and the timeout
    And I see no provider key and no sentence about Anthropic

  # --- what went wrong later, and where it is said ------------------------------------------------------------------

  @core
  Scenario: When a question to Claude fails, the page says why and since when
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    And the fake Anthropic says the credit balance is used up
    When someone asks @ai in a document whose owner allowed Claude
    And I open the AI page
    Then I read "Last error" and today's time
    And I read "The credit balance at Anthropic is used up."
    And I read that questions to Claude fail until credit is added or another provider is chosen

  @extended
  Scenario Outline: Every cause has its sentence for the administrator
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    And the fake Anthropic <fails>
    When someone asks @ai in a document whose owner allowed Claude
    And I open the AI page
    Then I read "<reason>"

    Examples:
      | fails                                | reason                                              |
      | refuses every key                    | Anthropic refused the key.                          |
      | says the credit balance is used up   | The credit balance at Anthropic is used up.         |
      | says the rate limit was reached      | Anthropic's rate limit was reached.                 |
      | says it is overloaded                | Anthropic is overloaded at the moment.              |
      | cannot be reached                    | Anthropic cannot be reached from this server.       |
      | does not know the model "claude-x"   | Anthropic does not know the model “claude-x”.       |

  @core
  Scenario: The last error stays until Claude has answered a question again
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    And the fake Anthropic says the credit balance is used up
    And someone asked @ai in a document whose owner allowed Claude
    When the fake Anthropic is topped up
    And I open the AI page
    Then I still read "Last error"
    When someone asks @ai in that document again and gets an answer
    And I reload the AI page
    Then I read "Last error: none"

  @core
  Scenario: The page does not switch to another provider by itself
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    And the fake Anthropic says the credit balance is used up
    When someone asks @ai in a document whose owner allowed Claude
    And I open the AI page
    Then it still says "Answering now:" and "Claude · claude-sonnet-5-5"
    And I read that the administrator decides: add credit, or choose another provider

  @extended
  Scenario: Changing the provider while a question is running is allowed and takes effect for the next one
    Given Claude is the server's AI provider with the key "sk-ant-test-a7Q2"
    And a question to Claude is running in a document whose owner allowed Claude
    When I choose "Local model" and press Apply
    Then the page says "Answering now:" and the local model
    And the question that was running ends as described in "claude-answers.feature"

  # --- being usable by everybody ------------------------------------------------------------------------------------

  @extended
  Scenario: The page can be used with the keyboard alone and says "remote" in words
    When I open the AI page
    Then every control on it can be reached with Tab and used with the keyboard
    And what answers is told by its words, "remote" included, never by a colour alone
    And a failed test or a last error is told in words, not by a colour alone

  @extended
  Scenario: The page is in my language
    Given my language is German
    When I open the AI page with Claude chosen
    Then every label, button and sentence on it is German
    And I read no English word that the catalogue has a German one for
