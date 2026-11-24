# Slides follow layouts; a change to what belongs to the layout is offered to every slide that follows it
# (E10.4, E10.5; the design is in notes/creates-templates-architecture.md, questions in layouts.review.md)
@draft
Feature: A slide follows a layout, and changing what belongs to the layout is offered to all slides that follow it

  # -- the start ---------------------------------------------------------------------------------------------
  @core @app:creates
  Scenario: A new presentation has one slide on the basic layout
    When I start a new presentation without choosing a template
    Then it has one slide
    And the slide follows the layout "Basic", which has no placeholder

  @core @app:creates
  Scenario: A new slide follows the layout of the slide before it
    Given a presentation whose second slide follows the layout "Two lists"
    When I add a slide after the second one
    Then the new slide follows "Two lists"

  @core @app:creates
  Scenario: Choosing another layout for a slide
    Given a slide on the layout "Basic" with a free text box
    When I choose the layout "Two lists" for it
    Then the slide has a title and two list boxes to fill in
    And the free text box is still where it was

  @extended @app:creates
  Scenario: An empty placeholder says what it is for while I edit, and is invisible otherwise
    Given a slide on "Two lists" whose title I have not filled in
    Then while I edit I see the hint "Title" where the title goes
    But in the slide show, in print and in an export there is nothing there

  # -- the offer: changing something that belongs to the layout --------------------------------------------
  @core @app:creates
  Scenario: Moving a placeholder on a slide offers to update the layout
    Given three slides on the layout "Two lists"
    When I move the left list on the second slide
    Then the second slide at once follows a new layout named "Two lists 2"
    And I am offered "Update layout · 3 slides instead", "New layout from this slide" and "Undo"
    And the first and the third slide have not changed

  @core @app:creates
  Scenario: Updating the layout changes every slide that follows it
    Given three slides on "Two lists", and I moved the left list on the second slide
    When I choose "Update layout · 3 slides instead"
    Then I see all three slides before and after, with the changed box outlined
    And when I confirm, all three slides show the left list where I put it
    And no layout "Two lists 2" is left

  @core @app:creates
  Scenario: Updating a layout that only one slide follows needs no preview
    Given one slide on "Two lists", and I moved the left list on it
    When I choose "Update layout · 1 slide instead"
    Then the layout changes at once, without a preview

  @core @app:creates
  Scenario: Making a new layout from a slide leaves the others alone
    Given three slides on "Two lists", and I moved the left list on the second slide
    When I choose "New layout from this slide" and name it "Wide list"
    Then I am asked what the layout is for, and I answer
    And the second slide follows "Wide list" and the other two still follow "Two lists" unchanged
    And "Wide list" is among the layouts I can choose for any slide

  @core @app:creates
  Scenario: Undo takes the offer back
    Given three slides on "Two lists", and I moved the left list on the second slide
    When I choose "Undo"
    Then the left list is where it was, the second slide follows "Two lists" again and no layout "Two lists 2" is left

  @core @app:creates
  Scenario: A box I added myself never triggers an offer
    Given a slide on "Two lists" with a text box I added
    When I move, resize and delete that box
    Then I am not offered anything

  @core @app:creates
  Scenario: Typing and formatting text in a placeholder never triggers an offer
    Given a slide on "Two lists" with the left list selected
    When I type into it and make a word bold
    Then I am not offered to update the layout

  @extended @app:creates
  Scenario: Changing the look of a placeholder is offered like moving it
    Given three slides on "Two lists"
    When I give the left list on the second slide a border
    Then I am offered "Update layout · 3 slides instead" and "New layout from this slide"

  @extended @app:creates
  Scenario Outline: Resizing and turning a placeholder on a slide are offered too
    Given three slides on "Two lists"
    When I <change> the left list on the second slide
    Then I am offered to update the layout or to make a new one
    Examples:
      | change |
      | resize |
      | turn   |

  @core @app:creates
  Scenario: Deleting a placeholder on a slide is offered, and the preview says what happens to the others
    Given three slides on "Two lists": the first has text in the left list, the second is the one I delete it on, the third has an empty left list
    When I delete the left list on the second slide and choose "Update layout · 3 slides instead"
    Then the preview says that one slide keeps its text as a free box and that one empty box is removed
    And when I confirm, the first slide keeps its text as a free box where it was and the third has no left list

  # -- other objects of the layout ---------------------------------------------------------------------------
  @core @app:creates
  Scenario: The logo of a layout is on every slide that follows it, and changing it is offered
    Given a layout with a logo and three slides that follow it
    When I move the logo on the second slide
    Then I am offered "Update layout · 3 slides instead" and "New layout from this slide"
    And when I update, the logo is in the new place on all three slides

  @extended @app:creates
  Scenario: Text of a layout object is offered for update when I leave the box
    Given a layout with the footer "Acme 2026" and three slides that follow it
    When I change the footer on the second slide to "Acme 2027" and keep typing
    Then I am offered nothing while I am in the box
    And when I leave the box I am offered "Update layout · 3 slides instead" and "New layout from this slide"

  @extended @app:creates
  Scenario: Deleting the logo on one slide is offered like any change
    Given a layout with a logo and three slides that follow it
    When I delete the logo on the second slide
    Then I am offered to update the layout for all three slides or to make a new layout

  # -- naming and tidiness ---------------------------------------------------------------------------------------
  @extended @app:creates
  Scenario: A layout nobody named and no slide follows goes away by itself
    Given a slide on the provisional layout "Two lists 2" that I never named
    When I choose another layout for the slide
    Then "Two lists 2" is no longer in the list of layouts

  @extended @app:creates
  Scenario: A layout I named stays when no slide follows it
    Given a layout "Wide list" that I named and that no slide follows
    Then it is still in the list of layouts, and I can hide it or delete it

  # -- changing a slide's layout ---------------------------------------------------------------------------------
  @core @app:creates
  Scenario: Boxes follow the placeholder with the same purpose when I change a slide's layout
    Given a slide on "Two lists" with text in the title and in the left list
    When I choose the layout "Title and one list" for it
    Then the text in the title is in the title of the new layout
    And the text in the left list is in the list of the new layout if that has the same purpose, otherwise it is a free box where it was

  # -- managing layouts --------------------------------------------------------------------------------------------
  @core @app:creates
  Scenario: Editing a layout changes every slide that follows it, without an offer
    Given three slides on "Two lists"
    When I choose Format ▸ Layout ▸ Edit this layout… and move the left list
    Then I see the layout as a slide, with how many slides follow it
    And all three slides show the left list in the new place when I close it

  @core @app:creates
  Scenario: All layouts… lists, renames, orders, hides and deletes layouts
    Given a presentation with several layouts
    When I choose Format ▸ Layout ▸ All layouts…
    Then I can rename a layout, move it up or down, hide it and delete it
    And a hidden layout is no longer offered when I choose a layout for a slide
    And a layout that comes with Claudia can only be hidden

  @core @app:creates
  Scenario: Deleting a layout that slides follow asks where they go
    Given two slides on "Wide list", the first with text in its left list
    When I delete "Wide list" and choose "Two lists" as the layout for its slides
    Then both slides follow "Two lists", boxes with the same purpose follow it and the others stay as free boxes where they were

  @extended @app:creates
  Scenario: Two layouts of one presentation never have the same name, and the placeholders of a layout never have the same purpose
    Given a layout "Two lists"
    When I try to name another layout "two lists", or to give two placeholders of one layout the purpose "Title"
    Then I am told the name or purpose is taken, and nothing changes

  # -- a presentation without slides ---------------------------------------------------------------------------
  @extended @app:creates
  Scenario: A presentation can have no slides, and I can still work on its layouts
    Given a presentation with one slide
    When I delete the slide
    Then Format ▸ Layout ▸ All layouts… still works
    And Insert ▸ New slide puts a new slide on the first visible layout

  # -- several people ------------------------------------------------------------------------------------------------
  @extended @two-users @app:creates
  Scenario: A slide a colleague adds while I update the layout follows the new layout too
    Given a colleague and I have the same presentation open, with three slides on "Two lists"
    When I update "Two lists" for all slides while my colleague adds a fourth slide on "Two lists"
    Then all four slides show the left list in the new place

  @extended @app:creates
  Scenario: One undo takes back the whole update
    Given I updated "Two lists" for three slides
    When I choose Edit ▸ Undo once
    Then the left list is back in its old place on all three slides

  # -- for everybody ---------------------------------------------------------------------------------------------------
  @core @app:creates
  Scenario: The preview and the offer can be used without a mouse and without seeing the thumbnails
    Given three slides on "Two lists", and I moved the left list on the second slide
    Then I can reach and choose every button of the offer with the keyboard
    And the preview has "Show as list", which says for each slide what changes in words

  @extended @desktop @app:creates
  Scenario: The same offer in the desktop clients
    Given the Linux, macOS or Windows client
    When I do what the scenarios above do
    Then I get the same offers, with the same words, and the same menus and keys
