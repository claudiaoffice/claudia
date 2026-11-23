# What the ai says when it has nothing to say, how long Claude may answer, and what the model is shown (CODE-81, CODE-82,
# D1564–D1566). Mock-up: notes/mockups/ai-provider-5-answer-length.svg. Architecture: notes/e7-2-architecture.md (diagram 3).
#
# Seen on 2026-11-23 on a real key: in a text a long request got "I have nothing to add.", in a presentation the model's list
# of requests came into the chat as text, while a one-sentence request worked. The causes: the model was shown doubled braces
# where a request is explained, an empty answer was dressed as an answer, and Claude's answers were cut at the local model's
# 512 tokens. Every scenario here fails today.
#
# Decided on 2026-11-23: an empty answer is "I could not comply."; Claude has its own answer length, 4096 by default,
# editable on the AI page; the local model's stays 512. Proposed, for a veto: when something was changed and the final answer is
# empty, the ai says "I made these changes: set_cells x1." (the list in the words the ai already uses when it stops).
@draft
Feature: The ai never answers with nothing, Claude may answer at length, and the model is shown plain requests

  Background:
    Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
    And a new computes document "budget" in which I am Anna, an owner
    And Anna allowed Claude in "budget"

  # --- the model is shown the form of a request (CODE-81) -----------------------------------------------------------

  @core
  Scenario Outline: What the model is shown has no doubled braces
    Given a new <document> "plan" in which I am Anna, an owner
    And Anna allowed Claude in "plan"
    When I write "@ai what can you do here?" in the chat
    Then the fake Anthropic received an example of a request written in plain braces
    And it received no doubled braces

    Examples:
      | document     |
      | workbook     |
      | text         |
      | presentation |

  @core
  Scenario: A text app answers a long request with the text in the document
    Given a new text "story" in which I am Anna, an owner
    And Anna allowed Claude in "story"
    And the fake Anthropic asks to add a story of 300 words as paragraphs and then answers "I wrote it."
    When I write "@ai write me a story about a boy, 300 words" in the chat
    Then the document holds all 300 words
    And the ai answers "I wrote it."

  @core
  Scenario: A presentation gets the text box, not the list of requests in the chat
    Given a new presentation "talk" in which I am Anna, an owner
    And Anna allowed Claude in "talk"
    And the fake Anthropic asks to add a text box that says "Hello" and then answers "Added."
    When I write "@ai add a textbox and write Hello in it" in the chat
    Then the slide holds a text box that says "Hello"
    And the chat shows no list of requests, only "Added."

  # --- an empty answer says so (CODE-82) -----------------------------------------------------------------------------

  @core
  Scenario: A model that answers with nothing is not dressed up as an answer
    Given the fake Anthropic answers with nothing at all
    When I write "@ai why is B7 an error?" in the chat
    Then the ai answers "I could not comply."
    And no cell was changed

  @core
  Scenario: A model that changed something and then says nothing is reported
    Given the fake Anthropic asks to put "52" in C7 and then answers with nothing at all
    When I write "@ai fix B7" in the chat
    Then the cell C7 holds 52
    And the ai answers "I made these changes: set_cells x1."

  @extended
  Scenario: The sentence is the same when the local model answers with nothing
    Given the server's AI provider is the local model, and it answers with nothing at all
    When I write "@ai why is B7 an error?" in the chat
    Then the ai answers "I could not comply."

  @extended
  Scenario: A short true answer is shown as it is
    Given the fake Anthropic answers "Done."
    When I write "@ai fix B7" in the chat
    Then the ai answers "Done."

  @extended
  Scenario: The list of changes is worded the same when the ai runs out of steps
    Given the fake Anthropic asks to put "52" in C7 and then keeps asking to look at the sheet
    When I write "@ai fix B7" in the chat
    Then the ai answers a sentence that says it stopped, and that it made these changes before stopping: "set_cells x1"

  # --- Claude's own answer length (CODE-82) ----------------------------------------------------------------------------

  @core
  Scenario: Claude may answer at length by default
    When I write "@ai why is B7 an error?" in the chat
    Then the fake Anthropic was allowed 4096 tokens of answer

  @core
  Scenario: The local model keeps its short limit
    Given the server's AI provider is the local model
    When I write "@ai why is B7 an error?" in the chat
    Then the local model was allowed 512 tokens of answer

  @core
  Scenario: The administrator sets Claude's answer length on the AI page
    Given I am the administrator and I have the AI page open with Claude chosen
    Then the field "Max answer length (tokens)" shows 4096
    When I change it to 8192 and press Apply
    And I write "@ai why is B7 an error?" in the chat
    Then the fake Anthropic was allowed 8192 tokens of answer

  @extended
  Scenario: Each provider keeps its own value on the page
    Given I am the administrator and I have the AI page open with Claude chosen
    When I change the field "Max answer length (tokens)" to 8192
    And I choose "Local model"
    Then the field shows 512
    When I choose "Claude" again
    Then the field shows 8192

  @extended
  Scenario: The page says how long that is in words
    Given I am the administrator and I have the AI page open with Claude chosen
    Then under the field I read "About 3,000 words"

  @extended
  Scenario: A length of nothing is refused and nothing is changed
    Given I am the administrator and I have the AI page open with Claude chosen
    When I change the field "Max answer length (tokens)" to 0 and press Apply
    Then I am told the answer length must be at least 1
    And Claude is still allowed 4096 tokens of answer

  @extended @unit:packages/claudia-server/tests/test_server_settings.py
  Scenario: Settings saved before this change read as 4096
    Given a settings file written by the version that had one answer length
    When the server starts
    Then Claude's answer length is 4096 and the local model's is what the file said
