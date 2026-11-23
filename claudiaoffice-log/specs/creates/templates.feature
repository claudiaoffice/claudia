# Templates: starting from one, saving one, the server's library, giving a finished deck another look
# (E10.4, E10.22, E10.23; the design is in notes/creates-templates-architecture.md, questions in templates.review.md)
@draft
Feature: A template is a presentation without slides that a new presentation starts from, and keeps no link to

  # -- starting -------------------------------------------------------------------------------------------------
  @core @app:creates
  Scenario: File ▸ New offers the templates of the server by what they are for
    Given the server has the templates "Conference talk" and "Weekly report"
    When I choose File ▸ New in creates
    Then I see a card for "Basic" first, then one for each template, each with what it is for

  @core @app:creates
  Scenario: A new presentation starts as a copy of the template
    Given the template "Conference talk" has three layouts and its own styles and colours
    When I start a new presentation from it
    Then I have one slide, on the first layout of the template
    And the presentation has those three layouts, those styles and those colours
    And I am the only one who can open it

  @core @app:creates
  Scenario: A presentation keeps no link to its template
    Given a presentation I started from "Conference talk"
    When I change a layout and a style in it
    Then the template "Conference talk" on the server is unchanged
    And when the administrator removes or replaces the template, my presentation looks and works as before

  @extended @app:creates
  Scenario: A presentation from the basic template has one layout without placeholders
    When I start a presentation from "Basic"
    Then it has one layout and one slide on it, and I can add layouts of my own

  # -- saving one ----------------------------------------------------------------------------------------------------
  @core @app:creates
  Scenario: Saving a presentation as a template gives a file without slides
    Given a presentation with eight layouts, its own styles and colours, and twelve slides with text
    When I choose Format ▸ Template ▸ Save as template…, name it "Conference talk", say what it is for and choose English
    Then I get a file with the eight layouts, the styles and the colours
    And it holds nothing of the twelve slides: not their text, their notes, their pictures, their history or the chat

  @extended @app:creates
  Scenario: Pictures that belong to the layout stay in the template, pictures of slides do not
    Given a presentation whose layout has a logo and whose second slide has a photo
    When I save it as a template and start a new presentation from the file
    Then the new presentation shows the logo on its layouts and does not hold the photo

  @extended @app:creates
  Scenario: Saving as a template is recorded as an export
    When I save a presentation as a template
    Then the record of exports shows it, like any other copy that leaves the document

  # -- the server's library -------------------------------------------------------------------------------------
  @core @app:creates
  Scenario: The administrator adds a template and everybody sees it in File ▸ New
    Given I am the administrator and have the file of "Conference talk"
    When I choose Server settings ▸ Templates ▸ Add template… and the check passes
    Then "Conference talk" is in the list of templates, and anyone who chooses File ▸ New sees it

  @core @app:creates
  Scenario: The administrator removes a template
    Given the server has the template "Weekly report"
    When I remove it in Server settings ▸ Templates
    Then it is no longer in File ▸ New, and presentations started from it are not touched

  @extended @app:creates
  Scenario Outline: A file that is not a template is refused, and nothing is added
    Given I am the administrator
    When I add <file> in Server settings ▸ Templates
    Then I am told why it is refused, and the list of templates is as before
    Examples:
      | file                                                    |
      | a presentation that still has slides                    |
      | a presentation without a layout                         |
      | a file whose name is already a template of this server |
      | a text document or a file that is no Claudia file       |

  @extended @app:creates
  Scenario: The basic template cannot be removed, and only an administrator can add one
    Given I am the administrator
    Then "Basic" has no Remove
    And a person who is not the administrator does not see Server settings ▸ Templates

  @extended @app:creates
  Scenario Outline: A template needs a name, a purpose and a language that is a tag
    Given a presentation with two layouts
    When I choose Format ▸ Template ▸ Save as template… and give <name>, <purpose> and <language>
    Then I am told what is missing or wrong, and no file is made
    Examples:
      | name                 | purpose   | language |
      | nothing              | for talks | en       |
      | Talks                | nothing   | en       |
      | Talks                | for talks | english! |
      | a name of 81 letters | for talks | en       |

  @extended @app:creates
  Scenario: A presentation says which template it came from
    Given I started a presentation from "Conference talk"
    Then Format ▸ Template says "Conference talk" and what it is for
    And a presentation I started from nothing says none

  @extended @app:creates
  Scenario: A template is a file anybody can check before it is added
    Given I am the administrator
    When I choose a template file in Server settings ▸ Templates ▸ Add template…
    Then I am told its name, what it is for, its language and its layouts before anything is added

  @extended @app:creates
  Scenario: A template that brought a history or a chat is kept without them
    Given the file of a template that was exported with its history and its chat
    When the administrator adds it
    Then the server keeps the template and nothing of the history or the chat

  @extended @app:creates
  Scenario: A template says in which language it is written
    Given a template written in German
    Then its card says German, and the names of the built-in template and of the layouts that come with Claudia are in my own language

  # -- giving a finished deck another look -------------------------------------------------------------------
  @core @app:creates
  Scenario: Change theme… gives the deck the styles and colours of a template and leaves its layouts alone
    Given a presentation with twelve slides and the server's template "Conference talk"
    When I choose Format ▸ Template ▸ Change theme…, choose its theme and confirm after the preview
    Then the styles and the colours are those of the theme, matched by what they are for
    And the layouts and every slide's layout are as before
    And one Undo takes it all back

  @core @app:creates
  Scenario: Change template… also takes the layouts, matched by name
    Given a presentation with slides on "Two lists" and "Title only", and a template with layouts of the same names
    When I choose Format ▸ Template ▸ Change template…, choose it and confirm after the preview
    Then the slides follow the template's layouts of those names
    And boxes follow the placeholder with the same purpose, and the others stay as free boxes where they were

  @extended @app:creates
  Scenario: What the template does not have stays in the presentation
    Given a presentation with a style "Quote" and a layout "Wide list" that the template does not have
    When I change the template
    Then "Quote" and "Wide list" are still there, and still mine

  @extended @app:creates
  Scenario: The deck is not linked to the template it was changed to
    Given I changed a presentation's template to "Conference talk"
    When the administrator replaces "Conference talk"
    Then my presentation is unchanged
