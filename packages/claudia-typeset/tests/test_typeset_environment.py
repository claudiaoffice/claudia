"""The environment a TeX process gets: nothing of ours, only what the platform needs to run programs (E3.10)."""

from claudia_typeset._environment import base_environment

WINDOWS_HOST = {
    "SYSTEMROOT": r"C:\Windows",
    "PATHEXT": ".COM;.EXE;.BAT;.CMD",
    "COMSPEC": r"C:\Windows\System32\cmd.exe",
    "APPDATA": r"C:\Users\ada\AppData\Roaming",
    "LOCALAPPDATA": r"C:\Users\ada\AppData\Local",
    "PROGRAMDATA": r"C:\ProgramData",
    "USERNAME": "ada",
    "CLAUDIA_SECRET": "hunter2",
    "PATH": r"C:\Users\ada\bin;C:\tools",
}
POSIX_HOST = {"HOME": "/home/ada", "CLAUDIA_SECRET": "hunter2", "PATH": "/home/ada/bin"}


def test_on_linux_and_macos_there_is_only_a_path():
    assert base_environment("linux", POSIX_HOST, "/work/job", ()) == {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    assert base_environment("darwin", POSIX_HOST, "/work/job", ()) == {"PATH": "/usr/local/bin:/usr/bin:/bin"}


def test_directories_to_search_come_first():
    env = base_environment("linux", POSIX_HOST, "/work/job", ["/opt/tex/bin", "/opt/poppler/bin"])
    assert env["PATH"] == "/opt/tex/bin:/opt/poppler/bin:/usr/local/bin:/usr/bin:/bin"


def test_nothing_of_the_hosts_own_environment_is_inherited_on_windows():
    env = base_environment("win32", WINDOWS_HOST, r"C:\work\job", ())
    assert "CLAUDIA_SECRET" not in env
    assert "USERNAME" not in env
    assert r"C:\Users\ada\bin" not in env["PATH"]


def test_windows_gets_what_it_needs_to_start_programs():
    env = base_environment("win32", WINDOWS_HOST, r"C:\work\job", ())
    assert env["SystemRoot"] == r"C:\Windows"
    assert env["PATHEXT"] == ".COM;.EXE;.BAT;.CMD"
    assert env["ComSpec"] == r"C:\Windows\System32\cmd.exe"


def test_windows_gets_the_places_tex_distributions_keep_their_settings():
    env = base_environment("win32", WINDOWS_HOST, r"C:\work\job", ())
    assert env["APPDATA"] == r"C:\Users\ada\AppData\Roaming"
    assert env["LOCALAPPDATA"] == r"C:\Users\ada\AppData\Local"
    assert env["ProgramData"] == r"C:\ProgramData"


def test_temporary_files_on_windows_go_into_the_job_folder():
    env = base_environment("win32", WINDOWS_HOST, r"C:\work\job", ())
    assert env["TEMP"] == env["TMP"] == r"C:\work\job"


def test_the_windows_path_is_the_search_directories_and_then_the_system_folders():
    env = base_environment("win32", WINDOWS_HOST, r"C:\work\job", [r"C:\texlive\bin\windows"])
    assert env["PATH"] == r"C:\texlive\bin\windows;C:\Windows\System32;C:\Windows"


def test_windows_without_the_usual_variables_still_gets_a_working_path():
    env = base_environment("win32", {}, r"C:\work\job", ())
    assert env["SystemRoot"] == r"C:\Windows"
    assert env["PATH"] == r"C:\Windows\System32;C:\Windows"
    assert "APPDATA" not in env
