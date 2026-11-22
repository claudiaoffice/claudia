# What a person gets when she asks @ai and Claude is the server's AI provider (E7.11, D32, D261, D262, D264, D266)
# Mock-up: notes/mockups/ai-provider-4-chat-panel.svg (also a page of penpot/claudia.penpot).
#
# The point of the story: a person asks @ai for support, suggestions and actions the same way she would ask a local model,
# and Claude acts the same way. So most scenarios are the local model's ones with another answerer; what is new is who may
# be asked and what the chat says about who answered. The fake Anthropic stands in for Anthropic (server/claude-as-ai-provider.feature).
#
# Decided on 2026-11-22: a failure of Claude is one sentence for the person ("<AI type> is not available at the moment. The
# administrator can see why.") and the reason is on the AI page; there is no automatic switch to another provider; the stop
# message is "Stopped: Claude was switched off."; the owners' consent only permits, so where Claude is not the server's
# provider the provider that is answers, and the chat says so (not an error).
Feature: @ai answers with Claude only where both the administrator and the owners agreed, and always says who answered

  Background:
    Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
    And the fake Anthropic answers "B7 divides by C7, which is empty. I'll divide by the 52 weeks."
    And a new computes document "budget" in which I am Anna, an owner
    And the sheet "Budget" has a formula in B7 that divides by the empty cell C7
    And Anna allowed Claude in "budget"

  # --- Claude answers -----------------------------------------------------------------------------------------------

  @core
  Scenario: Claude answers a question in the chat and the chat says so
    When I write "@ai why is B7 an error?" in the chat
    Then the ai answers "B7 divides by C7, which is empty. I'll divide by the 52 weeks."
    And the ai's row names "Claude" with a "remote" badge
    And under the answer I read "answered by Claude (remote)"

  @core
  Scenario: Claude is sent what the dialog says and nothing else
    Given the sheet "Salaries" has names and numbers that the question has nothing to do with
    When I write "@ai why is B7 an error?" in the chat
    Then the fake Anthropic received my question
    And it received what the ai looked at in the sheet "Budget"
    And it received nothing of the sheet "Salaries"
    And it received no password, no key and no list of the document's people

  @core
  Scenario: Claude looks and changes the document the way the local model does
    Given the fake Anthropic asks to look at "Budget!A1:F8" and then to put "52" in C7, and then answers "Done."
    When I write "@ai fix B7" in the chat
    Then the cell C7 holds 52
    And the History & Chat panel shows the change under the name "ai"
    And the ai answers "Done."
    When I undo the ai's change
    Then C7 is empty again

  @core
  Scenario: Claude acts with the rights of the person who asked
    Given Ben is a viewer of "budget"
    And the fake Anthropic asks to put "52" in C7
    When Ben writes "@ai fix B7" in the chat
    Then Ben is told that he can only look at this document
    And C7 is empty
    And the fake Anthropic was not asked anything

  @extended
  Scenario: Claude is asked one question at a time, in the order they were asked
    Given Ben is an editor of "budget"
    And the fake Anthropic is slow
    When I write "@ai first question" in the chat
    And Ben writes "@ai second question" in the chat
    Then the fake Anthropic is asked the first question and, when that is answered, the second
    And both are answered in that order, each to the one who asked

  @extended
  Scenario: The earlier chat goes with the next question, whoever answered it
    Given Anna did not allow Claude in "budget" yet
    And I asked @ai "what is in B7?" and the local model answered
    When Anna allows Claude in "budget"
    And I write "@ai and why is that?" in the chat
    Then the fake Anthropic received both my earlier question and the answer to it

  @extended
  Scenario Outline: Claude answers the same way in all three apps
    Given a new <document> "plan" in which I am Anna, an owner
    And Anna allowed Claude in "plan"
    When I write "@ai what is this?" in the chat
    Then the ai answers with what the fake Anthropic said
    And under the answer I read "answered by Claude (remote)"

    Examples:
      | document     |
      | workbook     |
      | text         |
      | presentation |

  @extended
  Scenario: Suggest mode treats Claude as it treats the local model
    Given I chose "Suggest first" in the panel
    And the fake Anthropic asks to put "52" in C7
    When I write "@ai fix B7" in the chat
    Then C7 is empty
    And the ai says what it would have done, as the local model does in this app

  # --- both approvals, or the server's own provider answers ---------------------------------------------------------

  @core
  Scenario: The administrator's approval alone is not enough
    Given Anna withdrew the consent for Claude in "budget"
    When I write "@ai why is B7 an error?" in the chat
    Then the ai is answered by the server's local provider, not by Claude
    And under the answer I read "answered by" and the local provider's name
    And I read "Claude is not allowed in this document. The owners can change that in Preferences ▸ AI…"
    And the fake Anthropic was not asked anything

  @core
  Scenario: The owners' consent alone is not enough, and it is not an error
    Given the administrator chose the local model and pressed Apply
    When I write "@ai why is B7 an error?" in the chat
    Then the ai is answered by the local model
    And under the answer I read "answered by" and the local model's name
    And I read no error line and no word about Claude being unavailable
    And the fake Anthropic was not asked anything

  @core
  Scenario: Without a local model the stand-in answers and says so
    Given the server has no model folder and the administrator did not allow Claude to anybody
    When I write "@ai why is B7 an error?" in the chat
    Then the answer is the stand-in's
    And under it I read "answered by" and "Scripted stand-in"

  @extended
  Scenario: Switching Claude off for a document takes effect for the next question
    Given Anna asked @ai a question and Claude answered
    When Anna withdraws the consent for Claude in "budget"
    And I write "@ai and now?" in the chat
    Then the answer is the local provider's
    And the fake Anthropic was asked only the first question

  # --- Claude is not available --------------------------------------------------------------------------------------

  @core
  Scenario: When Claude fails the person is told in one sentence and nobody else answers
    Given the fake Anthropic says the credit balance is used up
    When I write "@ai why is B7 an error?" in the chat
    Then the ai answers "Claude is not available at the moment. The administrator can see why."
    And under it I read "Claude · remote · no answer was made"
    And the local model was not asked
    And I read no word about credit

  @extended
  Scenario Outline: The same sentence for every cause
    Given the fake Anthropic <fails>
    When I write "@ai why is B7 an error?" in the chat
    Then the ai answers "Claude is not available at the moment. The administrator can see why."

    Examples:
      | fails                                |
      | refuses every key                    |
      | says the credit balance is used up   |
      | says the rate limit was reached      |
      | says it is overloaded                |
      | cannot be reached                    |
      | does not know the model "claude-x"   |

  @core
  Scenario: She can ask again when she likes
    Given the fake Anthropic says it is overloaded
    And I asked "@ai why is B7 an error?" and was told that Claude is not available
    When the fake Anthropic recovers
    And I write "@ai why is B7 an error?" in the chat again
    Then the ai answers "B7 divides by C7, which is empty. I'll divide by the 52 weeks."

  @extended
  Scenario: A change Claude made before it failed is kept and the failure is told
    Given the fake Anthropic asks to put "52" in C7 and then fails
    When I write "@ai fix B7" in the chat
    Then C7 holds 52
    And the ai answers "Claude is not available at the moment. The administrator can see why."

  @extended
  Scenario: A server that is not answering does not hold the others up forever
    Given the fake Anthropic never answers
    When I write "@ai why is B7 an error?" in the chat
    And the timeout of the AI page has passed
    Then the ai answers "Claude is not available at the moment. The administrator can see why."
    And a later question from another person is not stuck behind it

  @needs-decision
  Scenario: Running out of time is a cause of its own on the AI page
    Given the fake Anthropic never answers
    When I write "@ai why is B7 an error?" in the chat
    And the timeout of the AI page has passed
    And I open the AI page as the administrator
    Then I read "Anthropic did not answer within 60 seconds."

  # --- switching off while it works ---------------------------------------------------------------------------------

  @core @two-users
  Scenario: The owners switch Claude off while a question is running
    Given Jonas is an owner of "budget"
    And the fake Anthropic is slow and asks to look at "Budget!A1:F8" before it answers
    When I write "@ai why is B7 an error?" in the chat
    And Jonas withdraws the consent for Claude in "budget" while Claude is working
    Then the History & Chat panel says "Jonas switched Claude off for this document."
    And the ai says "Stopped: Claude was switched off."
    And under it I read "Claude · remote · stopped at its next step"
    And the fake Anthropic is asked nothing more for this question

  @core @two-users
  Scenario: After the stop the next question goes to the server's own provider
    Given a question to Claude was stopped because Jonas switched Claude off
    When I write "@ai and now?" in the chat
    Then the answer is the local provider's, with its name under it

  @extended @two-users
  Scenario: What was done before the stop stays, and is not undone
    Given the fake Anthropic asks to put "52" in C7, and then to look at the sheet again
    And Jonas is an owner of "budget"
    When I write "@ai fix B7" in the chat
    And Jonas withdraws the consent for Claude in "budget" after the change was made
    Then the ai says "Stopped: Claude was switched off."
    And C7 holds 52

  @extended
  Scenario: The administrator switching to another provider stops a running question the same way
    Given the fake Anthropic is slow
    When I write "@ai why is B7 an error?" in the chat
    And the administrator chooses the local model and presses Apply while Claude is working
    Then the ai says "Stopped: Claude was switched off."
    And the fake Anthropic is asked nothing more for this question

  # --- seeing who answers, usable by everybody ----------------------------------------------------------------------

  @extended
  Scenario: The badge is told in words, not by a colour
    Given Claude is the provider that answers in "budget"
    Then the ai's row reads "Claude · remote"
    And after the local provider answers, the row reads its name and "this server"
    And a screen reader reads the same words

  @extended
  Scenario: The chat is in my language
    Given my language is German
    And Claude is not available
    When I write "@ai why is B7 an error?" in the chat
    Then the sentence that tells me is German
    And so are "answered by" and "remote"
