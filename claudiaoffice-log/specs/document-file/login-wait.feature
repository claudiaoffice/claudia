# Wrong passwords make the next try wait (D1266, D1276, E2.7)
Feature: After a few wrong passwords the next try has to wait, and the wait is said

  Background:
    Given a new composes document "plan" in which I am Ann, an owner
    And Ann has closed the document

  @core @app:composes
  Scenario: After four wrong passwords I am told how long to wait and can go on afterwards
    When I try to open the document with a wrong password four times
    And I try once more
    Then I am told "Too many tries. Try again in 1 second."
    And the Open button cannot be pressed
    When the wait is over
    And I open the document with my own password
    Then the document is open

  @extended @app:composes
  Scenario: The right password does not get around the wait
    Given I tried a wrong password four times
    When I try once more with my own password
    Then I am told to wait, and the document stays closed

  @extended @unit:packages/claudia-server/tests/test_server_login_throttle.py
  Scenario: The waits grow, are capped, and are forgotten after a quiet quarter of an hour
    Given a wrong password is tried again and again from one address
    Then the waits are 1, 2, 4, 8, 16 and then 30 seconds at most per address, and 10 seconds at most per document and name
    And after fifteen quiet minutes the address starts again with three free tries

  @extended @unit:packages/claudia-server/tests/test_server_login_waits.py
  Scenario: The administrator's sign-in waits the same way
    Given a wrong administrator password was tried four times
    When the next try is made
    Then the server answers "too many tries" with the seconds to wait, before hashing anything
