# The Windows installer: what a person can do after installing (CODE-83, D746).
#
# "I installed for my profile only" is the installer's default for a person without administrator rights: everything
# lives under %LOCALAPPDATA%\Programs\Claudia Office, and no developer's checkout is anywhere near it. The first real
# install (2026-11-23) installed the server and the apps, and no icon opened a window.
#
# Written together with the fix, on the owner's order to fix CODE-83 (2026-11-23): to be reviewed by the owner.
# What is checked: that the launcher finds the apps the installer put there and prepares their window (unit tests; the
# install test of CI, which needs no display: windows.yml). Not checked by any automatic test: that a window then
# opens, which needs a desktop and the WebView2 Runtime (an advisory step of CI, and the owner's own install).
Feature: Claudia Office installed on Windows opens its apps

  @core @unit:clients/neutralino/tests/launch.test.ts @unit:clients/neutralino/tests/paths.test.ts @unit:tests/test_windows_packaging.py
  Scenario: The icon of an app finds the app after an install for my profile only
    Given I installed Claudia Office for my profile only
    When I start Claudia Composes from its icon
    Then it does not say that the app is missing or has not been built
    And the window of Claudia Composes opens
