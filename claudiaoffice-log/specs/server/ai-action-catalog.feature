# The action catalog: nothing a person can do in an app is forgotten when the ai is taught what it may do and see (E7.12, D1580–D1599).
# Mock-up: none (no screen). Architecture: notes/e7-12-architecture.md (diagrams 1 and 2).
#
# Who this is for: whoever adds or changes a feature. The checks are consistency checks between the catalog files
# (ai/action-catalog.md in each app and in the server), the code and the menu workbook. **No scenario here runs a model**: they
# say what the checks guarantee, and each is run by the test it names. Whether a real model uses what it is now given is what the
# owner's try with a real key shows, and is reported, not gated.
#
# Words: an action is something a person can do (glossary). In a catalog line the ai is "yes" (it can), "reserved" (left to
# people, with a reason) or "not yet" (a person can, the ai cannot). "Does" is a change, "looks" a read, "plumbing" is the wire
# between a client and the server and nobody's action.
#
# Defaults, marked for a veto: the catalog never runs in the server; the number of "not yet" lines is written in the file's header
# and the check wants it exact, so closing a gap lowers it and adding one is a visible edit; "yes" for a change means offered to
# the model and named in a skill; "yes" for a property means that changing it changes what the model is told; the eight reasons
# are permissions, own history, redaction, code, view state, leaving, account and ai itself.
#
# The last two groups of scenarios are the first two gaps closed (UX-76, UX-77): lists in composes, turning in creates. They use
# the scripted model of the existing prompt tests, which plays what a model would send.
@draft
Feature: The ai keeps up with what a person can do

  # --- every action has a line -------------------------------------------------------------------------------------

  @core @unit:tests/test_action_catalog.py
  Scenario Outline: Every method of an app has a line in its catalog, and every line has a method
    Given the action catalog of <app> and the server's
    Then the methods of <app> and the lines of its catalog are the same set

    Examples:
      | app      |
      | computes |
      | composes |
      | creates  |

  @core @unit:tests/test_action_catalog.py
  Scenario: A new method without a line fails and is named
    Given a method "flip_object" that the catalog of creates does not list
    When the catalog is checked
    Then the check fails and says that "flip_object" has no line in the catalog of creates

  @core @unit:tests/test_action_catalog.py
  Scenario: A line for a method that is gone fails and is named
    Given the catalog of creates has a line for "flip_object" and no such method exists
    When the catalog is checked
    Then the check fails and says that the line "flip_object" names no method

  @core @unit:tests/test_action_catalog.py
  Scenario: A line that cannot be read is named
    Given a catalog line whose "ai" column says "maybe"
    When the catalog is read
    Then it is refused naming the line and the three words that are allowed

  @core @unit:tests/test_action_catalog.py
  Scenario Outline: A change is "does" and a read is "looks"
    Given the catalog says "<kind>" for the method "<method>" of <app>, which <is>
    When the catalog is checked
    Then the check fails and says what the table says it is

    Examples:
      | app      | method        | kind    | is                  |
      | composes | replace_words | looks   | changes the document |
      | composes | paragraphs    | does    | only reads           |

  # --- "yes" is backed by the code ---------------------------------------------------------------------------------

  @core @unit:tests/test_action_catalog.py
  Scenario: A change the catalog says the ai can make must be offered to the model
    Given the catalog of composes says "yes" for "make_list"
    And "make_list" is not among the requests a model is offered in composes
    When the catalog is checked
    Then the check fails and says that "make_list" is not offered to a model

  @core @unit:tests/test_action_catalog.py
  Scenario: A change the ai can make must be taught in a skill
    Given the catalog of creates says "yes" for "rotate_object"
    And "rotate_object" is offered but no skill of creates names it
    When the catalog is checked
    Then the check fails and says that no skill teaches "rotate_object"

  @core @unit:tests/test_action_catalog.py
  Scenario: A look the ai can make must be offered, and needs no skill
    Given the catalog of computes says "yes" for the look "cells"
    Then "cells" is among the looks a model is offered in computes
    And no skill is needed for it

  @core @unit:tests/test_action_catalog.py
  Scenario: Reserved needs a reason, and a reserved action is never also "yes"
    Given a line that says "reserved" without a reason
    And a second line for an action that is in the list of requests a model is offered, which says "reserved"
    When the catalog is checked
    Then the check fails for both, naming them

  @core @unit:tests/test_action_catalog.py
  Scenario: The count of "not yet" lines is written in the header and must be exact
    Given the header of the catalog of composes says 30 and 31 lines say "not yet"
    When the catalog is checked
    Then the check fails and says to write 31 or to close a gap
    And closing a gap means the header goes down in the same commit

  # --- the menus name their methods --------------------------------------------------------------------------------

  @core @unit:tests/test_action_catalog.py
  Scenario: Every menu entry that has a place in an app names its methods
    Given a row of the menu workbook with a place in composes and an empty "Methods composes" cell
    When the catalog is checked
    Then the check fails and says which row, in which sheet, has no methods for composes

  @core @unit:tests/test_action_catalog.py
  Scenario: A menu entry may say that it only changes the view
    Given the row "View ▸ Zoom in" with "view only" for every app
    Then it is accepted
    And it names no method

  @core @unit:tests/test_action_catalog.py
  Scenario: A method named in the menu workbook must exist in that app
    Given a row whose "Methods creates" cell names "flip_object"
    When the catalog is checked
    Then the check fails and says that "flip_object" is no method of creates

  # --- seeing ------------------------------------------------------------------------------------------------------

  @core @unit:tests/test_action_catalog.py
  Scenario: Every property of a thing has a line
    Given an object in creates has a property "locked" with no line under "Seen"
    When the catalog is checked
    Then the check fails and says that "object.locked" has no line

  @core @unit:tests/test_action_catalog.py
  Scenario: A property the ai is said to see must change what the model is told
    Given the catalog of creates says "yes" for "object.rotation"
    And the sample slide has an object turned 270°
    When the rotation of that object in the answer of the look request is changed to 271
    Then the words the model is given change

  @core @unit:tests/test_action_catalog.py
  Scenario: A property the lens does not show fails the check
    Given the catalog says "yes" for a property that the lens does not put into words
    When the catalog is checked
    Then the check fails and says that the property is not shown

  @core @unit:tests/test_action_catalog.py
  Scenario: A sample that lacks the property cannot back a "yes"
    Given the catalog says "yes" for a property that is not in the answer for the sample document
    When the catalog is checked
    Then the check fails and says that the sample is too poor

  # --- the overview ------------------------------------------------------------------------------------------------

  @core @unit:tests/test_action_catalog.py
  Scenario: The overview across the three apps is generated and must be current
    Given the catalogs and the menu workbook
    When the overview is generated
    Then it equals notes/ai-action-catalog.md
    And it has a row per menu entry with "yes", "not yet", "reserved" or "view only" for each app

  @extended @unit:tests/test_action_catalog.py
  Scenario: Regenerating the overview after a catalog change is one command
    Given a catalog line changed from "not yet" to "yes"
    When "scripts/action_catalog.py --write" is run
    Then notes/ai-action-catalog.md shows the change and nothing else

  # --- gap closed: lists in composes (UX-76) -----------------------------------------------------------------------

  Rule: The ai can make and change lists in composes

    Background:
      Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
      And a new composes document "notes" with the paragraphs "Eggs", "Milk" and "Bread", in which I am Anna, an owner
      And Anna allowed Claude in "notes"

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: The ai is told how to make a list
      When I write "@ai make these three lines a numbered list" in the chat
      Then the fake Anthropic was offered the requests to make a list, continue one, start it at a number and indent an item
      And it was told how to make a list, with an example

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: The ai makes the three lines a numbered list
      Given the fake Anthropic answers by making the three paragraphs a numbered list and then says "Done."
      When I write "@ai make these three lines a numbered list" in the chat
      Then "Eggs", "Milk" and "Bread" are the items 1, 2 and 3 of one list
      And the chat shows what was done in the ai's own words

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: The model is shown which paragraphs are list items
      Given the fake Anthropic answers "Done."
      And "Milk" is the second item of a numbered list
      When I write "@ai what is the second item?" in the chat
      Then the fake Anthropic was shown that "Milk" is item 2 of a numbered list

    @extended @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: Someone who may only propose is not given the requests to change a list
      Given I am Ben, an editor, and I chose "Suggest first"
      When I write "@ai make these three lines a numbered list" in the chat
      Then the fake Anthropic was not offered the requests to make a list

  # --- gap closed: turning in creates (UX-77) ----------------------------------------------------------------------

  Rule: The ai can turn an object in creates, and can tell which way a shape points

    Background:
      Given a server whose AI provider is Claude, applied by the administrator with the sentence confirmed
      And a new creates document "signs" with a slide that has a triangle and a rectangle, in which I am Anna, an owner
      And Anna allowed Claude in "signs"

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: The ai is offered to turn an object, and told how
      When I write "@ai make an arrow pointing left" in the chat
      Then the fake Anthropic was offered the request to turn an object
      And it was told how to build a figure from several shapes, with the arrow as the example

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: The model is told how every shape looks unturned
      When I write "@ai make an arrow pointing left" in the chat
      Then the fake Anthropic was told that a triangle points up, and what a circle and a rectangle look like

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: An object that is not turned is said to be turned 0°
      When I write "@ai what is on the slide?" in the chat
      Then the fake Anthropic was shown the triangle as "turned 0°"

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: The ai builds an arrow pointing left from a triangle and a rectangle
      Given the fake Anthropic answers by turning the triangle so that its tip is on the left, placing the rectangle to its right, and says "Done."
      When I write "@ai make an arrow pointing left" in the chat
      Then the triangle's tip is on the left of the rectangle
      And the chat shows what was done in the ai's own words

    @core @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: A turned object that would leave the slide is refused in words the model can use
      Given the fake Anthropic answers by turning the triangle so that part of it would be off the slide, then reads the slide again
      When I write "@ai turn the triangle" in the chat
      Then the fake Anthropic was told that the object would leave the slide
      And the triangle is where it was

    @core @unit:tests/test_shape_library_looks.py
    Scenario: Every shape the product ships says how it looks unturned
      Given the shapes that come with the product
      Then each has a line saying how it looks unturned, such as "points up"

    @extended @unit:packages/claudia-server/tests/test_ai_lists_and_turning.py
    Scenario: A shape an administrator added without that line is listed by its name only
      Given an administrator's shape folder has a shape "star" with an outline and no line about its look
      When I write "@ai what shapes are there?" in the chat
      Then the fake Anthropic was shown "star" by its name, and every shipped shape with how it looks
