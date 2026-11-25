# The shortcuts of the Windows install (UX-82, D750).
#
# Found by the owner on the first real Windows install (2026-11-24): a console window of node stayed open for as long as
# an app ran, and showed only the start-up lines. The owner asked to hide it and to keep what it prints in a log file.
# Written together with the fix, for the owner's review. What is checked: the installer script's entries, the stage, the
# compile command (unit tests) and, on Windows in CI, that the compiled program passes on options and keeps both output
# streams. Not checked by any automatic test: that no console is ever seen, and what closing a window does to the processes.
Feature: An app of the Windows client starts without a console window and leaves a log

  @core @unit:tests/test_windows_packaging.py
  Scenario: Starting an app from its icon
    Given I installed Claudia Office
    When I start Claudia Computes from its Start menu entry or its desktop icon
    Then only the window of Claudia Computes appears
    And no console window opens or shows in the taskbar

  @core @unit:tests/test_windows_packaging.py
  Scenario: What the start prints is kept
    Given I started Claudia Computes
    Then %LOCALAPPDATA%\Claudia\computes\state\launcher.log holds what the start printed
    And the log of the start before is kept as launcher.log.old, unless a process of that start still holds it

  @unit:tests/test_windows_packaging.py
  Scenario: The start fails
    Given the launcher of an app stops with an error
    Then a message says so, with the place of the log and its last lines

  # CODE-96, D752
  @extended @unit:clients/neutralino/tests/launch.test.ts @unit:clients/neutralino/tests/build-shell.test.ts
  Scenario: A start that works logs no error of Neutralino
    Given I started an app of the Windows client and it works
    Then launcher.log holds no error of Neutralino about its resources or about /favicon.ico

  # CODE-97, D753
  @core @unit:clients/neutralino/tests/shell-page.test.ts @unit:clients/neutralino/tests/parent-watch.test.ts @unit:clients/neutralino/tests/core-process.test.ts @unit:tests/test_windows_packaging.py
  Scenario: A window that is closed or killed leaves no process of its app
    Given I started Claudia Composes and its window shows
    When I close the window, or end it from Task Manager
    Then no node.exe of Claudia Composes is running within half a minute
    # Closing is checked on a real window in CI (the step "The core of a window ends when its window is closed or killed");
    # the killed window there, and the killed window process in core-process.test.ts.
