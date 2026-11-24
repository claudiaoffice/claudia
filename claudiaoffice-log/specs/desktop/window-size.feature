# The size of the window of the Windows client on a scaled display (UX-77, D749).
#
# Found by the owner on the first real Windows install (2026-11-24): at a display scale of 200% (3840 x 1994) the window
# was half the size the page needs. Written together with the fix, for the owner's review. What is checked: the arithmetic
# and what the page asks Neutralino for (unit tests). Not checked by any automatic test: the real window on a real scaled
# display, which needs Windows.
Feature: The window of a desktop app shows the whole page at any display scale

  @core @unit:clients/neutralino/tests/window-size.test.ts @unit:clients/neutralino/tests/shell-page.test.ts
  Scenario: A scaled display
    Given my display is set to 200%
    When I start an app of the Windows client
    Then its window is as large, as seen by the page, as it is at 100%
    And it is centred on the screen

  @core @unit:clients/neutralino/tests/window-size.test.ts
  Scenario: A small screen
    Given my free screen is smaller than the window the app would like
    When I start an app of the Windows client
    Then the window takes nine tenths of the free screen and no less than its minimum size

  @unit:clients/neutralino/tests/shell-page.test.ts
  Scenario: The macOS client
    Given I start an app of the macOS client on a Retina display
    Then the window keeps the size of its config

  @core @unit:clients/neutralino/tests/shell-page.test.ts
  Scenario: The window does not answer the request for its size
    Given the window never answers a request to change its size
    When I start an app of the Windows client
    Then the app starts all the same
