# The server's administrators: naming the first one, resetting them, and what the settings pages promise about them
# (E3.11, SEC-12, D1370–D1376, UX-61). Mock-up: notes/mockups/sec12-first-administrator-setup-code.svg.
#
# "A server behind a proxy" is one started with --no-tls --behind-proxy on 127.0.0.1: the browser reaches it directly,
# and it counts as exposed (D1374). "The server's log" is what the server printed at start.
#
# Reviewed by the owner on 2026-11-20 (all proposals accepted): a server started by hand on 127.0.0.1 keeps its
# optional wording with the code field; wrong codes wait like the sign-in (three free tries, so the fifth is refused);
# the password file's first line is the password; set-aside administrators stay; the banner names a reset once; the
# demo's CLAUDIA_ADMIN and CLAUDIA_ADMIN_PASSWORD are the owner's to set; no menu entry; BITV as in the
# implementation note.
Feature: Only whoever runs a server can make the first administrator, and the pages say only what the server does

  # --- the setup code (D1370–D1372) -----------------------------------------------------------------------------------

  @core
  Scenario: The server says the setup code where only its operator looks
    Given a server behind a proxy that has no administrator
    Then the server's log gives a setup code and a link to the server settings with the code
    And the server's state folder has the setup code in a file only the server's account can read
    And the server's status does not contain the setup code

  @core
  Scenario: Naming the first administrator needs the setup code from the server's log
    Given a server behind a proxy that has no administrator
    When I open its server settings
    Then I am asked for a setup code, my name and a password
    When I type the setup code from the server's log, the name "anna" and a password, and press Create administrator
    Then I am signed in as "anna"
    And the server's state folder no longer has a setup code

  @core
  Scenario: Without the right code nobody becomes the first administrator
    Given a server behind a proxy that has no administrator
    When I open its server settings
    And I type the setup code "K7QM-4TXR-92H8", the name "mallory" and a password, and press Create administrator
    Then I am told that this is not the server's setup code
    And the server still has no administrator

  @core
  Scenario: The link in the log fills in the code and leaves the address bar
    Given a server behind a proxy that has no administrator
    When I open the link from the server's log
    Then the setup code is filled in and marked "From the link you opened"
    And the address bar shows no setup code

  @core
  Scenario: A server started by hand on this computer asks for the code too
    Given a server on 127.0.0.1 that has no administrator
    When I open its server settings
    Then I am asked for a setup code, my name and a password
    And the page offers "Skip for now"

  @extended
  Scenario: The code may be typed in lower case, with spaces and with O for zero
    Given a server behind a proxy that has no administrator
    When I open its server settings
    And I type the server's setup code in lower case with spaces, the name "anna" and a password, and press Create administrator
    Then I am signed in as "anna"

  @extended
  Scenario: Too many wrong codes make me wait
    Given a server behind a proxy that has no administrator
    When I open its server settings
    And I try 5 wrong setup codes
    Then I am told to try again in some seconds
    And the server still has no administrator

  @extended
  Scenario: Someone else was faster
    Given a server behind a proxy that has no administrator
    When I open its server settings
    And somebody else names "ben" the first administrator with the server's setup code
    And I type the setup code from the server's log, the name "anna" and a password, and press Create administrator
    Then I see the sign-in form with the line "Someone has named this server's first administrator in the meantime."

  @extended
  Scenario: A restart makes a new code and the old one stops working
    Given a server behind a proxy that has no administrator
    When the server is restarted
    Then the server's log gives a setup code that is not the one before
    And the setup code from before is refused

  @extended
  Scenario: A server behind a proxy says it can be reached from other computers
    Given a server behind a proxy that has no administrator
    When I open its server settings
    Then the page says the server can be reached from other computers
    And the page offers "Keep this server local for now"

  # --- the desktop apps (D1373) ----------------------------------------------------------------------------------------

  @core
  Scenario: In the desktop app nobody types a code
    Given a server on 127.0.0.1 that has no administrator
    And its page is shown by a desktop app that hands it the server's setup code
    When I open its server settings
    Then I see no setup code field
    And I can name myself "anna" with a password and am signed in

  @extended
  Scenario: The desktop app's code is refused after its server restarted: the field comes back
    Given a server on 127.0.0.1 that has no administrator
    And its page is shown by a desktop app that hands it a setup code the server does not have
    When I open its server settings
    Then I am asked for a setup code, my name and a password

  @core @unit:clients/linux/tests/test_bridge.py @unit:clients/neutralino/tests/bridge.test.ts
  Scenario: A desktop app hands over the code of its own server only
    Given a desktop app whose own server has no administrator
    When its window shows a page of its own server
    Then the app's welcome to the page carries the setup code from the server's state folder
    When its window shows a page of another server it was connected to
    Then the app's welcome carries no setup code

  @extended @unit:clients/linux/tests/test_private_server.py @unit:clients/neutralino/tests/private-server.test.ts
  Scenario: A desktop app reads the code again at every welcome
    Given a desktop app whose own server has no administrator
    When another window restarts the shared server
    Then the next welcome carries the new setup code

  @extended @unit:web/tests/setup-code.test.ts
  Scenario: A page talking to an older server shows no code field
    Given a server whose status does not say whether it needs a setup code
    When the setup page is shown
    Then there is no setup code field

  # --- resetting the administrators (D1375) ----------------------------------------------------------------------------

  @core
  Scenario: A reset removes the administrators and keeps every setting
    Given a server with the administrators "anna" and "ben", an access secret and an AI model folder set
    When the server is started with --reset-administrators
    Then the server's log says that "anna" and "ben" were removed
    And the server's log gives a setup code
    And the old administrators are kept aside in the server's state folder
    And the server has no administrator
    When I name "carla" the first administrator with the new setup code
    Then the access secret and the AI model folder are as before

  @core
  Scenario: The next administrators are told about the reset until one of them dismisses it
    Given a server whose administrators "anna" and "ben" were reset and "carla" was named
    When "carla" opens Access & documents
    Then she reads that the administrators were reset from the server's console, with the date and "anna and ben"
    And she is told to rotate the access secret if they should no longer know it
    When she presses Dismiss
    Then the note is gone, also after the page is opened again

  @extended
  Scenario: A reset does not touch the documents
    Given a server with the administrator "anna" and a composes document "report" of Ann
    When the server is started with --reset-administrators
    Then Ann opens "report" with her name and password as before

  # --- naming the first administrator at start (D1376) -----------------------------------------------------------------

  @core
  Scenario: --admin names the first administrator at start, and no code is made
    Given a password file with the password "a-long-password"
    When a server with no administrator is started with --admin "anna" and that password file
    Then the server's log says "anna" was named at start
    And the server's state folder has no setup code
    And "anna" signs in to the server settings with "a-long-password"

  @extended
  Scenario: --admin changes nothing when the server has administrators
    Given a server with the administrator "anna" and the password "the-old-password"
    When it is started with --admin "anna" and a password file with "a-new-password"
    Then the server's log says that the server has administrators and --admin changed nothing
    And "anna" signs in with "the-old-password"

  @extended
  Scenario: --reset-administrators and --admin together put a new first administrator in place
    Given a server with the administrators "anna" and "ben"
    When it is started with --reset-administrators, --admin "carla" and a password file
    Then the server's administrators are "carla" only
    And the server's state folder has no setup code

  @extended @unit:tests/test_docker_entrypoint.py
  Scenario: The container names its first administrator from the platform's secret variables
    Given the container's variables CLAUDIA_ADMIN "anna" and CLAUDIA_ADMIN_PASSWORD "a-long-password"
    When the container starts
    Then the server is started with --admin "anna" and a password file that only the server's account can read
    And the server's environment has no CLAUDIA_ADMIN_PASSWORD

  # --- what the pages promise (UX-61) ----------------------------------------------------------------------------------

  @core @unit:web/tests/admin-wording.test.ts
  Scenario: Naming the first administrator does not promise a way back that does not exist
    Given a server that has no administrator yet
    When I open its server settings
    Then the page does not call the access secret a recovery key
    And it says that only someone with access to the computer the server runs on can name a new first administrator

  @core @unit:web/tests/admin-wording.test.ts
  Scenario: The access secret is described as what it does
    Given I am signed in as an administrator
    When I open Access & documents
    Then the access secret is described as what lets people make documents and see their list
    And it is not called a recovery key
