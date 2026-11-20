# How large a new picture or container is, and making any object larger (D1229, D1332, D1333, D1334)
Feature: A new picture or container comes out at a size I can see and work with, in every app
  As a writer, I want what I put in to be neither so large that it fills the page nor so small that it is lost next to
  my words, and I want to make any object larger or smaller with its handles. "The body text" is the body text style of
  the document; its font size is 12 pt in composes, 13 px in computes and 40 units of the slide in creates, in each
  app's own units (D1332). The scenarios that need a picture drawn by LaTeX skip, with a reason, on a server that has no
  LaTeX set up; the same sizes are checked without a browser by the unit tests named below.

  # ================================================================ the least and the most

  @core @firefox @app:composes
  Rule: A short formula comes out at least as tall as my body text (D1332)

    # measured 2026-11-20: XeLaTeX draws "E = mc^2" 43 by 12; it came out in a frame of 43 by 20, letterboxed 12 high,
    # under the label "LaTeX"
    Scenario: A formula of one line
      Given a new composes document "sizes" in which I am Ann, an owner
      When I insert a LaTeX container and write "E = mc^2"
      Then the container is at least as tall as the font size of the body text, and at least 20
      And its frame has the proportions of its picture, so the formula fills it
      And the label "LaTeX" is not drawn over the formula

  @unit:packages/claudia-server/tests/test_server_new_object_sizes.py
  Rule: The server sizes the first picture of a container and a picture from a file the same way in all three apps

    Scenario Outline: A short formula in <app>
      Given a new <app> document
      When a container is added with fit and its first picture is 50 by 10
      Then the container is <least> high and <wide> wide, the picture's proportions at the body text's height

      Examples:
        | app      | least | wide |
        | composes | 20    | 100  |
        | computes | 20    | 100  |
        | creates  | 40    | 200  |

    Scenario: A large diagram is no larger than 420 by 240, with its proportions
      When a container is added with fit and its first picture is 1000 by 1000
      Then the container is 240 by 240

    Scenario: A long one-line formula: the least wins over the most, up to the room it has
      When a container is added with fit in composes and its first picture is 2000 by 10
      Then the container is as tall as the body text and as wide as the text column

    Scenario: Only the first picture is fitted; a size I set is kept
      Given a container that has its first picture
      And I made it 300 by 100
      When its text changes and a new picture comes
      Then it is still 300 wide

    Scenario: A tiny picture from a file
      When a picture of 8 by 8 pixels is added with fit
      Then it is as tall as the body text, and square

    Scenario: A picture copied and pasted keeps the size it was copied at
      When a picture of 40 by 40 is added without fit
      Then it is 40 by 40

  @core @e2e:objects.cjs
  Rule: A new container in computes and creates starts at 420 by 240, as in composes (D1333)

    Scenario: Insert ▸ Container ▸ LaTeX in computes and in creates
      When I insert a LaTeX container
      Then it is 420 wide and 240 high before its first picture comes

  @extended @app:composes
  Rule: A new container does not cover my words (D1334)

    Scenario: The words go on below a new container
      Given a new composes document "sizes" in which I am Ann, an owner
      And I have typed a paragraph of three lines
      When I insert a LaTeX container in the middle of the first line
      Then no word of the paragraph lies under the container

  # ================================================================ the handles

  # B6 (2026-11-20, size 1): in composes no object could be resized: the frame followed the pointer and jumped back on
  # release ("w must be an integer"), because the page measures a frame in fractions of a pixel.
  @core @firefox @app:composes
  Rule: The corner handle makes any object larger, as one step of the history

    Scenario Outline: A <kind> grows with its corner
      Given a new composes document "sizes" in which I am Ann, an owner
      And I have inserted a <kind>
      When I drag its lower right corner 100 to the right and 50 down
      Then it is larger, and stays so when I let go
      And the history has one entry for the new size
      And no message says it could not be done

      Examples:
        | kind             |
        | text box         |
        | rectangle        |
        | LaTeX container  |

    Scenario: A handle on the left edge makes it wider to the left
      Given a new composes document "sizes" in which I am Ann, an owner
      And I have inserted a text box
      When I drag its left edge 60 to the left
      Then it is wider, and stays so when I let go

  @core @e2e:objects.cjs
  Rule: The handles scale every kind of object in computes and creates as well
    Scenario: The battery of web/e2e/objects.cjs, step 4, for every kind in every app
      Then each object grows with its corner, keeping its proportions where its kind has them

  @extended @unit:web/tests/geometry.test.ts
  Rule: The least any object may be stays 20 units (D1332)
    Scenario: The handle stops at 20 by 20
      When I drag a corner far past the opposite one
      Then the object is 20 by 20, in whole units
