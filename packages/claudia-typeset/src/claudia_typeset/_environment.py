"""The environment of a sandboxed process: a few variables the platform needs, nothing of the server's own."""

import ntpath
from collections.abc import Iterable, Mapping

POSIX_PATH = "/usr/local/bin:/usr/bin:/bin"

# Variables Windows needs to start programs, and the places where TeX distributions keep their settings
# (MiKTeX reads and writes them). Nothing else is passed on; names are matched without regard to case.
_WINDOWS_PASSED = ("SystemRoot", "PATHEXT", "ComSpec", "APPDATA", "LOCALAPPDATA", "ProgramData")
_WINDOWS_FALLBACK_ROOT = r"C:\Windows"


def _lookup(host: Mapping[str, str], name: str) -> str | None:
    wanted = name.casefold()
    for key, value in host.items():
        if key.casefold() == wanted:
            return value
    return None


def base_environment(
    platform: str, host: Mapping[str, str], cwd: object, search_path: Iterable[object]
) -> dict[str, str]:
    """The variables a process starts with: ``search_path`` directories first, then the system's own.

    ``platform`` is ``sys.platform``, ``host`` the server's environment (only read for what Windows needs) and
    ``cwd`` the job folder, which becomes the temporary folder on Windows.
    """
    first = [str(directory) for directory in search_path]
    if platform != "win32":
        return {"PATH": ":".join([*first, POSIX_PATH])}
    environment = {name: value for name in _WINDOWS_PASSED if (value := _lookup(host, name)) is not None}
    root = environment.setdefault("SystemRoot", _WINDOWS_FALLBACK_ROOT)
    environment["TEMP"] = environment["TMP"] = str(cwd)
    environment["PATH"] = ";".join([*first, ntpath.join(root, "System32"), root])
    return environment
