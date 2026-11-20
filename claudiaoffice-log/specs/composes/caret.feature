# The caret at the edges of a composes text (D1350)
Feature: The arrow keys keep the caret in the text
  As a writer, I want Up on the first line and Down on the last line to leave the caret in my text, at its start or its
  end, so that I never seem to be writing on a line that is not there.

  Background:
    Given a new composes document "caret" in which I am Ann, an owner

  # B7 (2026-11-20, size 2): Up in front of the first word seemed to put the caret on a line above the text (Firefox);
  # what was typed then still went in front of the first word. Right after typing, Up went to the end of the line.
  @core @firefox
  Rule: Up on the first line goes to the start of the text, Down on the last line to its end

    Scenario: Up in front of the first word stays in front of it
      Given I have written "First" and it is saved
      And my caret is at the start of "First"
      When I press the up arrow
      Then the caret is at the start of "First"
      When I type "Start"
      Then the text reads "StartFirst"

    # measured 2026-11-20 in Chromium: Home before "First" was sent put the caret in front of it, but once it was sent the
    # caret was behind it again, and what came next was typed at the end ("FirstStart")
    Scenario: Right after typing, Home and Up go to the start, and what I type goes there
      Given I have written "First"
      When I press Home and the up arrow at once
      Then the caret is at the start of "First"
      When I type "Start"
      Then the text reads "StartFirst"

    Scenario: Down on the last line goes to the end of the text
      Given I have written "First" and it is saved
      And my caret is at the start of "First"
      When I press the down arrow
      Then the caret is at the end of "First"

  @extended
  Rule: With Shift, the selection reaches the start or the end

    Scenario: Shift+Up on the first line selects to the start of the text
      Given I have written "First words" and it is saved
      And my caret is at the end of "First words"
      When I press Shift and the up arrow
      Then "First words" is selected

    Scenario: Up and Down between paragraphs are not touched
      Given I have written "First" and "Second" in two paragraphs and it is saved
      And my caret is at the start of "Second"
      When I press the up arrow
      Then the caret is in "First"
