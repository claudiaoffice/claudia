# The macOS package: install, open, update, uninstall (E8.5; D1625-D1629 proposed).
#
# Approved by the owner on 2026-11-25 (his answers are in the scenarios and in D1625-D1629). An unsigned package for Apple Silicon, macOS 14 and newer, installed for
# all people of the Mac. No Mac runner is connected: the package is built on Linux in CI (2026-11-26) and these
# scenarios are run by packaging/macos/test-install.sh on the owner's Mac (or a macOS virtual machine), and by unit
# tests of the package's parts on any system, which their tags name. Opening an unsigned package ("Open Anyway") needs
# a person and is checked by hand. The last scenario was added on 2026-11-26 (the package in CI): to be reviewed.
Feature: claudia installed on a Mac from one package

  @core
  Scenario: Installing claudia
    Given a Mac with Apple Silicon and macOS 14 or newer, with neither Python nor Node installed
    When I open the claudia package, allow it in Privacy & Security, and install it with an administrator's password
    Then "claudia composes", "claudia computes" and "claudia creates" are in Applications
    And "uninstall claudia" is in Applications ▸ Utilities

  @core
  Scenario: Opening an app after installing
    Given I installed claudia
    When I open claudia composes from Applications
    Then its window opens on "Private on this computer"
    And the Dock shows one icon for it, named "claudia composes"
    And macOS shows no warning that the app cannot be opened or checked

  @core
  Scenario: The service is not installed unless I choose it
    When I install claudia without changing its components
    Then no claudia service runs
    And no place is called "Shared on this computer"

  @core
  Scenario: Installing the service
    When I install claudia and choose the claudia service under "Customize"
    Then after the Mac has restarted, the claudia service runs before anyone has logged in
    And every person of the Mac finds "Shared on this computer"

  @core
  Scenario: Updating keeps everything that is mine
    Given claudia is installed with the service
    And there are documents in "Private on this computer" and in "Shared on this computer"
    When I install a newer claudia package
    Then all those documents are still there
    And the claudia service runs the newer version, with the settings its administrator made

  @core
  Scenario: Uninstalling leaves only documents and settings
    Given claudia is installed with the service
    When I open "uninstall claudia" and give an administrator's password
    Then the three apps, "uninstall claudia" and the claudia service are gone
    And no process of claudia runs
    And my documents and the shared documents are still on the Mac
    And each person's ~/Library/Caches/Claudia is gone, and her settings and logs are still there
    And its last words were "claudia is removed. These folders are left: the shared documents in /Library/Application Support/Claudia/shared/documents, and each person's own documents and settings in ~/Library/Application Support/Claudia. Delete them if you no longer need them."

  @extended
  Scenario: Uninstalling while an app is open
    Given claudia computes is open
    When I uninstall claudia
    Then I am told "claudia's apps that are open, also those of other people of this Mac, are closed." before anything is removed
    And after uninstalling, no process of claudia runs

  @extended
  Scenario: Closing an app leaves no process of its window
    Given claudia composes is open
    When I quit it
    Then no process of its window runs within half a minute

  @extended
  Scenario: What an app prints when it starts is kept
    Given I opened claudia composes
    Then ~/Library/Logs/Claudia/composes.log holds what its start printed

  @extended
  Scenario Outline: The installer says which version it installs
    When I open the claudia package of version <version>
    Then the installer's title is "claudia <version>"

    Examples:
      | version |
      | 0.5.0   |
      | 1.12.3  |

  @extended
  Scenario: The installer speaks my language
    Given my Mac's language is German
    When I open the claudia package
    Then its welcome and licence pages are in German

  @extended
  Scenario: A Mac the package is not made for
    Given a Mac with an Intel processor, or with macOS 13 or older
    When I open the claudia package
    Then the installer says that claudia needs a Mac with Apple Silicon and macOS 14 or newer
    And nothing is installed

  @core
  Scenario Outline: Every release offers the package to download
    When the version <version> is tagged as "v<version>"
    Then its GitHub release offers "claudia-office-<version>-macos-arm64.pkg" for download, next to the Windows installer and the Debian package
    And the package was built and checked by CI, without a Mac

    Examples:
      | version |
      | 0.5.0   |
      | 1.12.3  |
      | 2.0.0   |
