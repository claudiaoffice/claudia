# Deleting and hiding a style (E1.10; D226, D780, D785, D1300, D1301)
Feature: Deleting a style never leaves anything without a style
  As a writer, I want to delete a style of my own and be told first what that does to my text, so that nothing in my
  document is left without a style or changes its look without my knowing.

  # All styles… and its Delete dialog are one component in all three apps (D209); composes is where it is driven here.

  Background:
    Given a new composes document "styles" in which I am Ann, an owner
    And the paragraph "A note that stands out" has a style of my own, "Pull note", that makes it bold

  Rule: Assigning another style is the first way, and it says what will look different

    @core @firefox
    Scenario: Assigning Body text says first that one paragraph will look different
      When I ask to delete "Pull note" in All styles
      Then the way chosen is "Assign another style", with "Body text" to take its place
      And I am told that 1 paragraph will look different
      When I delete the style
      Then "A note that stands out" has the style "Body text" and is not bold
      And "Pull note" is no longer among the styles

    @core @firefox
    Scenario: Undo brings the deleted style back, and the look with it
      Given I have deleted "Pull note" by assigning "Body text"
      When I choose Undo in the message that says it was deleted
      Then "A note that stands out" has the style "Pull note" and is bold
      And "Pull note" is among the styles again

  Rule: Re-basing keeps every look; only the styles based on the deleted one move (D1300)

    @core @firefox
    Scenario: Re-basing on Body text keeps the paragraph bold, under a new style that waits for a name
      When I ask to delete "Pull note" in All styles
      And I choose to re-base it on "Body text"
      Then I am not told that anything will look different
      When I delete the style
      Then "A note that stands out" has the style "Pull note (kept)" and is bold
      And "Pull note (kept)" waits for a name

    @extended
    Scenario: A style based on the deleted one keeps its name and its look
      Given the paragraph "A louder note" has a style of my own, "Loud pull note", based on "Pull note", that makes it italic
      When I delete "Pull note" by re-basing it on "Body text"
      Then "A louder note" has the style "Loud pull note" and is bold and italic
      And "A note that stands out" has the style "Pull note (kept)" and is bold

    # D1301. The look can only fail to be held under a style that sets something with no neutral value (a font, a size,
    # a colour, an alignment) which the deleted style's look does not set. Every style a person can make is built on the
    # plain style of its kind, which sets all of those, so no screen can reach this case today; the unit tests check it.
    @extended @unit:packages/claudia-core/tests/test_style_deletion.py::test_a_look_that_cannot_be_held_refuses_the_deletion_and_changes_nothing @unit:web/tests/style-deletion.test.ts
    Scenario: A style the look could not be kept under is not offered for re-basing, and the reason is given
      When I ask to delete a style whose look one of the other styles could not hold
      Then that style cannot be chosen to re-base on
      And the dialog names it with the property that could not be held
      And "Assign another style" is still offered

  Rule: Built-in styles can only be hidden

    @extended
    Scenario: Body text cannot be deleted, only hidden and shown again
      When I open All styles
      Then "Pull note" offers Delete and "Body text" offers only Hide
      When I hide "Body text"
      Then "Body text" is no longer among the styles
      When I choose to show hidden styles
      Then "Body text" is among the styles again, marked hidden
      When I show "Body text"
      Then "Body text" is among the styles again
