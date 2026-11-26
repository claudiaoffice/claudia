@app:composes
Feature: My role in a document, and deleting a document from the list of documents
  File ▸ Manage ▸ My Role… is the one place for what a person does about their own role (the workbook, D1608): an owner
  hands the document over to an editor, that editor accepts it there, and anyone can leave the document. Deleting a
  document from the server left the document's menus for the front page: each document of the list on this server has
  a Delete button, confirmed by the owner's name and password (UX-98).

  @core
  Scenario: An owner hands the document over through My Role…, and the editor accepts it there
    Given a new composes document in which I am Ann, an owner, and Ben is an editor
    When I choose File ▸ Manage ▸ My Role… and hand the document over to "ben" with my password
    Then I am told that ben has been asked to take over the document
    When Ben opens the document, chooses File ▸ Manage ▸ My Role… and accepts with his password
    Then Ben's My Role… says that he is an owner of the document

  @core
  Scenario: An editor leaves the document through My Role…
    Given a new composes document in which I am Ann, an owner, and Ben is an editor
    When Ben opens the document, chooses File ▸ Manage ▸ My Role… and leaves it with his password
    Then Ben is back at the list of documents
    And Ben cannot open the document any more

  @core
  Scenario: An owner deletes a document from the list of documents on this server
    Given a new composes document in which I am Ann, an owner
    When I close the document and press Delete for it in the list on this server
    And I confirm with my name and password
    Then the document is no longer in the list on this server
    And nobody can open it any more

  @extended
  Scenario: Only an owner can delete a document from the list
    Given a new composes document in which I am Ann, an owner, and Ben is an editor
    When Ben goes to the list of documents, presses Delete for the document and confirms with his name and password
    Then Ben is told that only an owner can delete it
    And the document is still in the list on this server
