# The size of the window of the Windows client on a scaled display (UX-77, D749).
#
# Found by the owner on the first real Windows install (2026-11-24): at a display scale of 200% (3840 x 1994) the window
# was half the size the page needs. Written together with the fix, for the owner's review. What is checked: what the
# launcher puts into the config the window starts from (unit tests). Not checked by any automatic test: the real window on
# a real scaled display, which needs Windows. A first version, which had the page ask the window for its size, did nothing
# on the owner's machine and is gone.
Feature: The window of a desktop app shows the whole page at any display scale

  @core @unit:clients/neutralino/tests/launch.test.ts @unit:clients/neutralino/tests/core-command.test.ts
  Scenario: A scaled display
    Given my display is set to 200%
    When I start an app of the Windows client
    Then its window is as large, as seen by the page, as it is at 100%

  @extended @unit:clients/neutralino/tests/launch.test.ts @unit:clients/neutralino/tests/core-command.test.ts
  Scenario: The sizes of the config are what they were afterwards
    Given I started an app of the Windows client, or its window could not be started
    Then the config of the app is as it was before, with no window option left in it

  @unit:clients/neutralino/tests/launch.test.ts
  Scenario: The macOS client
    Given I start an app of the macOS client on a Retina display
    Then the window keeps the size of its config
