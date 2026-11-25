"""Whether a program an administrator names for typesetting is the program it should be (SEC-16, D2002).

The server runs ``xelatex`` and ``pdftocairo`` for every formula and picture it typesets, so a setting that names any
other runnable file would make the server run that file again and again. A setting is therefore accepted only after
the program, run once in the typesetter's sandbox, says who it is.
"""

import tempfile
from collections.abc import Sequence
from pathlib import Path

from claudia_typeset import EngineUnavailable, Limits, SandboxError, resolve_program, run_sandboxed

from .i18n import msg

_LIMITS = Limits(seconds=10, memory_mb=512, output_mb=1)

#: How each program is asked who it is, and how the first words of its answer must begin.
_ASK: dict[str, tuple[Sequence[str], str]] = {
    "xelatex": (("--version",), "XeTeX"),
    "pdftocairo": (("-v",), "pdftocairo version"),
}


async def check_identity(setting: str, configured: str | None) -> None:
    """Make sure the program configured for ``setting`` names itself as that program. Nothing configured is fine: the
    program is then looked up on the PATH when it is needed. Raises ``ValueError`` with a sentence for a person when
    the program cannot be found, does not run, or is not the program ``setting`` asks for."""
    if configured is None or configured.strip() == "":
        return
    arguments, banner = _ASK[setting]
    try:
        program = resolve_program(setting, configured, setting)
        with tempfile.TemporaryDirectory() as folder:
            done = await run_sandboxed([str(program), *arguments], cwd=Path(folder), env={}, limits=_LIMITS)
    except (EngineUnavailable, SandboxError) as error:
        raise ValueError(str(error)) from error
    if not any(line.strip().startswith(banner) for line in done.output.splitlines()):
        raise ValueError(
            msg(
                "{program} does not say it is {setting}: asked with {asked}, it should answer with a line that "
                "begins “{banner}”",
                program=configured,
                setting=setting,
                asked=" ".join(arguments),
                banner=banner,
            )
        )
