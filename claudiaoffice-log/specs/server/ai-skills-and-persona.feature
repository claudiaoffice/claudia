# How the ai is taught to work in each app: the persona and the recipes (E7.2, D9, D24, D1560–D1563).
# Mock-up: none (nothing new on a page). Architecture: notes/e7-2-architecture.md (diagrams 1 and 2).
#
# What a person gets from it: the ai asks for the right requests in the right form, it looks in the help before it answers
# how to use Claudia, and it is never told how to do something it may not do. The fake Anthropic (server/claude-as-ai-provider.feature)
# lets a scenario say what the model was told; whether a real model obeys is what the owner's real-key test shows.
#
# Proposed defaults, marked for a veto: a recipe is only given when every request it uses is offered to this asker; composes
# has a twin recipe "Propose a rewrite" for suggest mode; the persona and the recipes are English, and read by the model only.
@draft
Feature: The ai is told how to work in the app it is in, and only what it may do there

  Background:
    Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
    And the fake Anthropic answers "Done."
    And a new computes document "budget" in which I am Anna, an owner
    And Anna allowed Claude in "budget"

  # --- the persona and the recipes of the app ------------------------------------------------------------------------

  @core
  Scenario: The ai is told how to write values and formulas in a workbook
    When I write "@ai put 52 in C7" in the chat
    Then the fake Anthropic was told how to write values and formulas
    And it was told to answer briefly, in my language, and never to invent anything

  @core
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

  @extended
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

  @core
  Scenario: A person who may only look gets no recipe for changing
    Given Ben is a viewer of "budget"
    When Ben writes "@ai what is in B7?" in the chat
    Then the fake Anthropic was told it can only look
    And it was told nothing about how to write values and formulas

  @extended
  Scenario: In suggest mode the text app is taught to propose, not to rewrite
    Given a new text "essay" in which I am Anna, an owner
    And Anna allowed Claude in "essay"
    And I chose "Suggest first" in the panel
    When I write "@ai tighten the second paragraph" in the chat
    Then the fake Anthropic was told how to propose a rewrite
    And it was told nothing about how to rewrite a passage

  @extended
  Scenario: In suggest mode a workbook is taught no way to change anything
    Given I chose "Suggest first" in the panel
    When I write "@ai fix B7" in the chat
    Then the fake Anthropic was told it can only look
    And it was told nothing about how to write values and formulas

  # --- the help first --------------------------------------------------------------------------------------------------

  @core
  Scenario: How to use Claudia is answered from the help
    Given a new text "essay" in which I am Anna, an owner
    And Anna allowed Claude in "essay"
    And the fake Anthropic first asks the help for "table of contents", then opens the topic it found, then answers with what the topic says
    When I write "@ai how do I make a table of contents?" in the chat
    Then the ai answers with what the topic says
    And the text of "essay" is unchanged
    And the History & Chat panel shows no change by "ai"

  @core
  Scenario: A person who may only look can ask how to use Claudia too
    Given Ben is a viewer of "budget"
    And the fake Anthropic first asks the help for "sort", then opens the topic it found, then answers with what the topic says
    When Ben writes "@ai how do I sort a column?" in the chat
    Then the ai answers with what the topic says

  @extended
  Scenario: The help is read in the language of the person
    Given I work in German
    And the fake Anthropic first asks the help for "Sortieren", then opens the topic it found, then answers with what the topic says
    When I write "@ai wie sortiere ich?" in the chat
    Then the fake Anthropic read the German text of the topic

  @extended
  Scenario: The help of another app is not offered
    Given the fake Anthropic asks the help for "speaker notes"
    When I write "@ai how do I write speaker notes?" in the chat
    Then the fake Anthropic is told that the help has nothing about speaker notes in a workbook

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
  Scenario: Every recipe has a worked example
    Given the files of an app
    Then each recipe has an example of the request it teaches

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
    Then it refuses to start and names the recipe
