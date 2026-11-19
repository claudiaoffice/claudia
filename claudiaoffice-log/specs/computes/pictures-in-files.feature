# Pictures on a sheet reach the XLSX and ODS file (D1233)
@io:packages/claudia-computes-io/tests/test_pictures.py
Feature: A picture floating on a sheet is in the file I export, where it is, as big, as turned and as described

  @core @app:computes
  Scenario Outline: A picture is pinned to its cell
    Given a workbook with a picture on cell B3, 200 by 100, and a chart on the same sheet
    When I export it as <format>
    Then the file shows the picture at B3 with that size, in front of or behind the chart as I stacked them
    And Excel, LibreOffice and Claudia all show it there
    Examples:
      | format |
      | xlsx   |
      | ods    |
  @core @app:computes
  Scenario Outline: A turned picture stays turned
    Given a picture turned by 30°
    When I export it as <format>
    Then it is turned by 30° about its centre in the file
    Examples:
      | format |
      | xlsx   |
      | ods    |
  @core @app:computes
  Scenario Outline: What the picture says to someone who cannot see it is kept
    Given a picture named "Logo" that says "The company's logo", and a decorative one
    When I export it as <format>
    Then the name and the description are on the picture, and the decorative one says so (xlsx) or is reported (ods)
    Examples:
      | format |
      | xlsx   |
      | ods    |
  @extended @app:computes
  Scenario Outline: An SVG picture and a rendered container
    Given a container whose picture is an SVG, and one that was never drawn
    When I export it as <format> with and without a rasteriser
    Then with one the picture is a PNG; without one the file is told "svg-fallback" and the picture is the SVG
    And the container that was never drawn is left out, with "rendering-pending"
    Examples:
      | format |
      | xlsx   |
      | ods    |
  @extended @app:computes
  Scenario: A picture added to an imported workbook is reported until the patch of a kept file learns it
    Given a workbook imported from XLSX or ODS
    When I add a picture and export it again
    Then the answer says one "object" was not written (CODE-66)
