"""The typesetter: a job in, a checked SVG out (E3.4, E3.10).

Each job gets a private folder, a clean environment and the font catalogue's own ``fonts.conf``;
XeLaTeX makes a PDF, ``pdftocairo`` turns it into SVG, and the SVG is checked before it is kept.
Results are cached by what they were made from, failures never are.
"""

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from claudia_fonts import Catalogue, JobFonts, write_fontconfig

from .cache import ResultCache, cache_key
from .diagnosis import Diagnosis, Step, hint_for
from .job import Job, Limits, Mode
from .programs import HELP_TOPIC, EngineUnavailable, resolve_program
from .sandbox import OutputTooLarge, SandboxError, run_sandboxed
from .source import Built, FontUnavailable, TexError, build_source, parse_log
from .svg import check_svg

_XELATEX_FLAGS = ("-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error")
_VERSION_LIMITS = Limits(seconds=10, memory_mb=512, output_mb=1)
_MAIN = "main.tex"


class TypesetFailed(Exception):
    """The engine ran and could not typeset the source; ``error`` says what and where."""

    def __init__(self, error: TexError) -> None:
        where = f" (line {error.line})" if error.line else ""
        super().__init__(f"{error.message}{where}")
        self.error = error


@dataclass(frozen=True)
class Typeset:
    """A typeset picture and whether it was found in the cache."""

    svg: str
    cached: bool


class Typesetter:
    """Typesets jobs with XeLaTeX and the fonts of one catalogue, keeping its files in ``directory``.

    ``xelatex`` and ``pdftocairo`` say where the programs of the person's own LaTeX installation are: a full path, the
    folder they are in, or a name to look up on the PATH (see `resolve_program`). They are looked for when they are
    first needed, so a server can start without LaTeX and say what is missing when someone asks for a formula.
    """

    def __init__(
        self,
        catalogue: Catalogue,
        directory: str | Path,
        *,
        limits: Limits | None = None,
        xelatex: str | os.PathLike[str] | None = None,
        pdftocairo: str | os.PathLike[str] | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._directory = Path(directory).resolve()
        self._limits = limits or Limits()
        self._settings = {"xelatex": xelatex, "pdftocairo": pdftocairo}
        self._cache = ResultCache(self._directory / "results")
        self._fonts: JobFonts | None = None
        self._version: str | None = None

    async def engine_version(self) -> str:
        """The first line of what XeLaTeX says about itself; part of every cache key."""
        if self._version is None:
            self._directory.mkdir(parents=True, exist_ok=True)
            program = self._program("xelatex")
            done = await self._run([str(program), "--version"], self._directory, {}, _VERSION_LIMITS)
            lines = done.output.strip().splitlines()
            if done.returncode != 0 or not lines:
                raise EngineUnavailable(f"{program} does not report a version.")
            self._version = lines[0].strip()
        return self._version

    async def typeset(self, job: Job) -> Typeset:
        """Typeset ``job``, or find it in the cache.

        Raises `FontUnavailable` before anything runs, `TypesetFailed` when TeX rejects the source, `Timeout` or
        `OutputTooLarge` when a limit is passed, and `UnsafeOutput` when the picture is not only drawing.
        """
        built = build_source(job, self._catalogue)
        key = cache_key(job, engine=await self.engine_version(), fonts=self._catalogue.digest)
        kept = self._cache.get(key)
        if kept is not None:
            return Typeset(kept, cached=True)
        svg = await self._typeset(built)
        self._cache.put(key, svg)
        return Typeset(svg, cached=False)

    def _job_fonts(self) -> JobFonts:
        if self._fonts is None:
            folder = self._directory / "fontconfig" / self._catalogue.digest[:16]
            folder.mkdir(parents=True, exist_ok=True)
            self._fonts = write_fontconfig(self._catalogue, folder, self._directory / "font-cache")
        return self._fonts

    def _program(self, setting: str) -> Path:
        return resolve_program(setting, self._settings[setting], setting)

    def _search_path(self) -> list[Path]:
        """The folders of the programs in use, so that the engine finds its own helpers (xdvipdfmx and others)."""
        folders: list[Path] = []
        for setting in self._settings:
            folder = self._program(setting).parent
            if folder not in folders:
                folders.append(folder)
        return folders

    async def _run(self, argv: list[str], cwd: Path, env: dict[str, str], limits: Limits):  # noqa: ANN202
        try:
            return await run_sandboxed(argv, cwd=cwd, env=env, limits=limits, search_path=self._search_path())
        except FileNotFoundError as error:
            raise EngineUnavailable(f"{argv[0]} could not be started ({error.strerror or error}).") from error

    async def diagnose(self) -> Diagnosis:
        """Try the installation and say what works and what does not, with what to do about it.

        Never raises for the ordinary ways an installation is wrong. The test document is set every time and is not
        taken from the cache, because the point is to try the installation as it is now.
        """
        steps = [await self._check_program("xelatex"), await self._check_program("pdftocairo")]
        steps.append(self._check_fonts())
        if all(step.ok for step in steps):
            steps.append(await self._check_test_document())
        return Diagnosis(tuple(steps))

    async def _check_program(self, setting: str) -> Step:
        try:
            program = self._program(setting)
            if setting == "xelatex":
                version = await self.engine_version()
            else:
                done = await self._run([str(program), "-v"], self._directory, {}, _VERSION_LIMITS)
                if done.returncode != 0:
                    raise EngineUnavailable(f"{program} did not run properly: {done.output.strip()[:200]}")
                version = done.output.strip().splitlines()[0] if done.output.strip() else "version unknown"
        except (EngineUnavailable, SandboxError) as error:
            return Step(setting, False, str(error), f"See the help topic {HELP_TOPIC}.")
        return Step(setting, True, f"{program}: {version}")

    def _check_fonts(self) -> Step:
        try:
            build_source(Job(Mode.MATH, "x"), self._catalogue)
        except FontUnavailable as error:
            hint = (
                f"Add the Latin Modern fonts of your TeX installation to the font catalogue (help topic: {HELP_TOPIC})."
            )
            return Step("fonts", False, str(error), hint)
        return Step("fonts", True, f"{len(self._catalogue.families())} font families in the catalogue")

    async def _check_test_document(self) -> Step:
        try:
            await self._typeset(build_source(Job(Mode.MATH, r"x^2 + \frac{1}{2}"), self._catalogue))
        except TypesetFailed as error:
            return Step("test document", False, str(error), hint_for(error.error.message))
        except SandboxError as error:
            return Step("test document", False, str(error), "The installation is too slow or too big for the limits.")
        return Step("test document", True, "a formula was typeset")

    async def _typeset(self, built: Built) -> str:
        jobs = self._directory / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(dir=jobs))
        try:
            return await self._convert(built, folder)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    async def _convert(self, built: Built, folder: Path) -> str:
        (folder / _MAIN).write_text(built.text, encoding="utf-8")
        environment = {
            **self._job_fonts().environment,
            "HOME": str(folder),
            "openin_any": "p",  # paranoid: no absolute paths, no "..", no dot files
            "openout_any": "p",
            "shell_escape": "f",
            "SOURCE_DATE_EPOCH": "0",  # the same source gives the same PDF
            "FORCE_SOURCE_DATE": "1",
        }
        done = await self._run(
            [str(self._program("xelatex")), *_XELATEX_FLAGS, _MAIN], folder, environment, self._limits
        )
        pdf = folder / "main.pdf"
        if done.returncode != 0 or not pdf.exists():
            error = parse_log(
                done.output, first_line=built.first_line, line_count=built.line_count, job_folder=str(folder)
            )
            if error is None:
                message = "TeX stopped without a message" if done.returncode != 0 else "TeX produced no output"
                error = TexError(message, None)
            raise TypesetFailed(error)
        converted = await self._run(
            [str(self._program("pdftocairo")), "-svg", "-f", "1", "-l", "1", "main.pdf", "main.svg"],
            folder,
            {"HOME": str(folder)},
            self._limits,
        )
        svg = folder / "main.svg"
        if converted.returncode != 0 or not svg.exists():
            raise TypesetFailed(TexError("could not convert the result to a picture", None))
        if svg.stat().st_size > self._limits.output_mb * 1024 * 1024:
            raise OutputTooLarge(f"the picture is larger than {self._limits.output_mb} MB")
        return check_svg(svg.read_text(encoding="utf-8"))
