# How the ai is taught to work in each app: the persona and the recipes (E7.2, D9, D24, D1560–D1563).
# Mock-up: none (nothing new on a page). Architecture: notes/e7-2-architecture.md (diagrams 1 and 2).
#
# What a person gets from it: the ai asks for the right requests in the right form, it looks in the help before it answers
# how to use Claudia, and it is never told how to do something it may not do. The fake Anthropic (server/claude-as-ai-provider.feature)
# lets a scenario say what the model was told; whether a real model obeys is what the owner's real-key test shows.
#
# Defaults, marked for a veto: a recipe is only given when every request it uses is offered to this asker; composes has a twin
# recipe "Propose a rewrite" for suggest mode (an owner who acts is given it too: both requests are offered to her); the persona
# and the recipes are English, and read by the model only; the ai reads the help in English and answers in the asker's language.
# A person who "may only look" is an editor in suggest mode in an app where nothing can be proposed yet (computes, creates):
# a viewer cannot write in the chat at all.
#
# Every scenario is checked by the test it names; the scripted model of those tests is what the fake Anthropic would be.
Feature: The ai is told how to work in the app it is in, and only what it may do there

  Background:
    Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
    And the fake Anthropic answers "Done."
    And a new computes document "budget" in which I am Anna, an owner
    And Anna allowed Claude in "budget"

  # --- the persona and the recipes of the app ------------------------------------------------------------------------

  @core @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario: The ai is told how to write values and formulas in a workbook
    When I write "@ai put 52 in C7" in the chat
    Then the fake Anthropic was told how to write values and formulas
    And it was told to answer briefly, in my language, and never to invent anything

  @core @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario Outline: Each app gets its own recipes and not the others'
    Given a new <document> "plan" in which I am Anna, an owner
    And Anna allowed Claude in "plan"
    When I write "@ai what can you do here?" in the chat
    Then the fake Anthropic was told how to <own>
    And it was told nothing about how to <other>

    Examples:
      | document     | own                         | other                       |
      | workbook     | write values and formulas   | add a slide                 |
      | text         | rewrite a passage           | write values and formulas   |
      | presentation | add a slide                 | rewrite a passage           |

  @extended @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario Outline: Every recipe of the first list is there
    Given a new <document> "plan" in which I am Anna, an owner
    And Anna allowed Claude in "plan"
    When I write "@ai what can you do here?" in the chat
    Then the fake Anthropic was told how to <recipe>

    Examples:
      | document     | recipe                              |
      | workbook     | write values and formulas           |
      | workbook     | add a sheet                         |
      | workbook     | find and replace                    |
      | text         | write text into an empty document   |
      | text         | rewrite a passage                   |
      | text         | apply a style                       |
      | text         | build a table                       |
      | presentation | add a slide                         |
      | presentation | write words in a text box           |
      | presentation | draw a shape                        |
      | presentation | write speaker notes                 |
      | presentation | move and resize an object           |

  # --- only what the asker may do ------------------------------------------------------------------------------------

  @core @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario Outline: A person who may only look gets no recipe for changing, but is still told who the ai is
    Given a new <document> "plan" in which I am Anna, an owner
    And Anna allowed Claude in "plan"
    And Ben is an editor of "plan" who chose "Suggest first"
    When Ben writes "@ai what is here?" in the chat
    Then the fake Anthropic was told it can only look
    And it was told nothing about how to <recipe>
    And it was told to answer briefly, in Ben's language, and never to invent anything

    Examples:
      | document     | recipe                    |
      | workbook     | write values and formulas |
      | presentation | add a slide               |

  @extended @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario: In suggest mode the text app is taught to propose, not to rewrite
    Given a new text "essay" in which I am Anna, an owner
    And Anna allowed Claude in "essay"
    And I chose "Suggest first" in the panel
    When I write "@ai tighten the second paragraph" in the chat
    Then the fake Anthropic was told how to propose a rewrite
    And it was told nothing about how to rewrite a passage

  # --- the help first --------------------------------------------------------------------------------------------------

  @core @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario: How to use Claudia is answered from the help
    Given a new text "essay" in which I am Anna, an owner
    And Anna allowed Claude in "essay"
    And the fake Anthropic first asks the help for "table of contents", then opens the topic it found, then answers with what the topic says
    When I write "@ai how do I make a table of contents?" in the chat
    Then the ai answers with what the topic says
    And the text of "essay" is unchanged
    And the History & Chat panel shows no change by "ai"

  @core @unit:packages/claudia-server/tests/test_server_ai_prompt.py
  Scenario Outline: A person who may only look can ask how to use Claudia too
    Given a new <document> "plan" in which I am Anna, an owner
    And Anna allowed Claude in "plan"
    And Ben is an editor of "plan" who chose "Suggest first"
    When Ben writes "@ai how do I find and replace?" in the chat
    Then the fake Anthropic was offered the requests to search the help and to open a topic, among those that only look

    Examples:
      | document     |
      | workbook     |
      | presentation |

  # --- the files themselves (checked by tests, not by a window) --------------------------------------------------------

  @extended @unit:packages/claudia-server/tests/test_ai_guidance.py
  Scenario: The persona and the recipes of an app together are at most 6,000 characters
    Given the files of an app
    Then its persona and all its recipes together are at most 6,000 characters

  @extended @unit:packages/claudia-server/tests/test_ai_guidance.py
  Scenario: Every recipe names requests that its app really offers
    Given the files of an app
    Then each recipe names at least one request
    And every request it names is one that the app offers a model, to look or to change

  @extended @unit:packages/claudia-server/tests/test_ai_guidance.py
  Scenario: Every recipe has a worked example that the server accepts
    Given the files of an app
    Then each recipe has an example of the request it teaches
    And the example gives the parameters of that request and all it needs
    And the server carries it out on a document that holds what it names

  @extended @unit:packages/claudia-server/tests/test_ai_guidance.py
  Scenario: The lines every persona shares are the same in all three apps
    Given the persona files of the three apps
    Then the lines they share word for word are the same in each

  @extended @unit:packages/claudia-server/tests/test_ai_guidance.py
  Scenario: An app that ships both files has them in the installed package
    Given the three apps are installed as packages
    Then each has a persona file and a recipes file in the package itself

  @extended @unit:packages/claudia-server/tests/test_ai_guidance.py
  Scenario: A recipe that names no request stops the server at start
    Given a recipes file with a recipe without the line that names its requests
    When the server loads it
    Then loading is refused with a message that names the recipe
