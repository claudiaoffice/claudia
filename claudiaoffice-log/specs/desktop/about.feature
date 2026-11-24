# Help > About in the Windows and macOS clients (CODE-84, D748).
#
# Those two clients draw their menu with the system, but have no About dialog of their own: the entry is sent to the page,
# which shows its About dialog. The Linux client has a native one. Found by the owner on the first real Windows install
# (2026-11-24): About worked in an open document and did nothing on the start page.
# Written together with the fix, for the owner's review.
Feature: Help > About opens on every page of the desktop client

  @core @unit:web/tests/open.test.ts
  Scenario: About on the start page
    Given I started an app of the Windows client and I am on its start page
    When I choose Help > About
    Then the About dialog of the app opens, with its name and its links

  @core @unit:web/tests/document-menus.test.ts
  Scenario: About in an open document
    Given I have a document open in an app of the Windows client
    When I choose Help > About
    Then the About dialog of the app opens, with its name and its links
