"""Run Claudia's end-to-end tests on this computer: set it up, then run what you ask for.

    ./run-e2e.sh setup                  # only get this computer ready (see "What setup does"); then stop
    ./run-e2e.sh core                   # the specs tagged @core: the journeys that must always work
    ./run-e2e.sh extended               # the specs tagged @core and @extended: everything in specs/
    ./run-e2e.sh regression             # the older scripts (web/e2e/*.cjs) and tests/e2e, as CI runs them
    ./run-e2e.sh all                    # regression, then every spec
    ./run-e2e.sh core --browser both    # in Chromium and in Firefox
    ./run-e2e.sh core --feature tables  # only the spec files with "tables" in their name
    ./run-e2e.sh regression --only composes --only lists    # only these scripts
    ./run-e2e.sh --list                 # what there is, and how long each part usually takes
    ./run-e2e.sh setup --dry-run        # say what setup would do, change nothing

What the words mean
    core        specs/ scenarios tagged @core, in the browsers chosen with --browser (default: chromium).
    extended    the same plus those tagged @extended, i.e. every scenario that is not waiting for a decision.
    specs       an alias of "extended".
    regression  exactly what CI runs in its end-to-end job, from one list (SCRIPTS below, D1452): pytest tests/e2e
                (with the specs), every Node script in web/e2e against real servers, and the Windows and macOS
                client's window. These only drive Chromium; --browser does not change that.
    all         regression, then specs.
    setup       only the setup below.

A spec scenario whose step has no code yet is skipped with its words; the list of skips is shown at the end of
every run. `--list` counts the scenarios from the files each time, so it cannot go out of date.

What setup does (every run does it first, and skips what is already done; --no-setup skips all of it)
    1. checks that uv, node (22 or newer) and npm are installed, and says how to get them if not;
    2. python packages: `uv run` already installed them from uv.lock before this script started;
    3. packages: `npm ci` in web/ and in clients/neutralino/ when node_modules is missing or package-lock.json changed;
    4. the web app: `npm run build` when web/.output is missing or older than web/app (or with --rebuild);
    5. browsers for Playwright, for Python and for Node (they keep separate versions): chromium, and firefox when
       --browser asks for it. On Linux a browser may also need system libraries; this script does not use sudo, it
       prints the one command to run yourself;
    6. fonts and hyphenation patterns the server hands out for print and PDF, fetched once into .claudia/e2e/
       (needs the internet; without them the print tests are the only ones that suffer, and it says so).
Nothing outside this checkout is touched, except Playwright's own browser cache in your home folder.

Where things go
    .claudia/e2e/shots/     a screenshot per script or scenario (--shots DIR to change)
    .claudia/e2e/logs/      the full output of every script; the last lines are shown when one fails
    .claudia/e2e/           fonts, hyphenation patterns, the servers' temporary folders
It runs servers on ports 8765-8768, so stop a ./start.sh that is running first; the script checks and tells you.

Exit status: 0 everything passed, 1 something failed, 2 setup failed or an option was wrong.
Linux and macOS. On Windows use WSL.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
CLIENT = ROOT / "clients" / "neutralino"  # the Windows and macOS client, whose windows two scripts test
STATE = ROOT / ".claudia" / "e2e"
SPECS_TESTS = ROOT / "tests" / "e2e" / "specs"
BUILT = WEB / ".output" / "public" / "index.html"
NODE_MAJOR = 22
PORTS = {"computes": 8765, "composes": 8766, "creates": 8767}
MODELS = {
    "computes": "claudia_computes.model:WorkbookModel",
    "composes": "claudia_composes:TextModel",
    "creates": "claudia_creates:SlideModel",
}
START_SECONDS = 90

# Where a script of web/e2e runs: against one of the three shared one-app servers on 8765-8767 (or "all" of them),
# against a server it starts itself ("own"), against a server with house fonts on 8768 ("fonts"), or in the window of
# the Neutralino client built for Windows or macOS, which starts its own server too ("windows", "macos").
SHARED = ("computes", "composes", "creates", "all")
OWN = "own"
FONTS = "fonts"
CLIENT_WINDOWS = ("windows", "macos")


@dataclass(frozen=True)
class Script:
    """A browser script of web/e2e: the npm script ``e2e:<name>`` ("demo" is plain ``e2e``), where it runs, minutes."""

    name: str
    runs: str
    minutes: int = 1

    @property
    def npm(self) -> str:
        """The name of its npm script in web/package.json."""
        return "e2e" if self.name == "demo" else f"e2e:{self.name}"


# The one list of the browser scripts (D1452): `./run-e2e.sh regression` runs them in this order, and CI runs
# `./run-e2e.sh regression`, so a computer and CI run the same. A script in web/package.json that is missing here fails
# tests/test_ci_workflow.py.
SCRIPTS: list[Script] = [
    Script("demo", "computes"),
    Script("pointing", "computes"),
    Script("regions", "computes"),
    Script("grid-a11y", "computes"),
    Script("describe", "computes"),
    Script("redaction", "computes"),
    Script("composes", "composes"),
    Script("composes-wrap", "composes"),
    Script("styling", "composes"),
    Script("style-delete", "composes"),
    Script("print", "composes", 2),
    Script("lists", "composes"),
    Script("dock-text", "composes"),
    Script("slides", "creates"),
    Script("creates-styles", "creates"),
    Script("print-creates", "creates", 2),
    Script("describe-creates", "creates"),
    Script("present", "creates"),
    Script("dock", "creates"),
    Script("keys", "all"),
    Script("objects", "all", 3),
    Script("resilience", OWN),
    Script("recovery", OWN),
    Script("search", OWN),
    Script("pivots", OWN),
    Script("passwords", OWN),
    Script("details", OWN),
    Script("admin-fonts", FONTS),
    Script("windows-shell", "windows", 2),
    Script("macos-shell", "macos", 2),
]


class Failure(Exception):
    """Something the person has to fix before going on; the message says what and how."""


@dataclass
class Result:
    name: str
    ok: bool
    seconds: float
    note: str = ""


def pytest_command(path: str) -> list[str]:
    """pytest on ``path``, its summary naming what failed or broke and what it skipped and why (PROC-52)."""
    return [sys.executable, "-m", "pytest", "-rfEs", path]


class Runner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.results: list[Result] = []
        STATE.mkdir(parents=True, exist_ok=True)
        self.logs = STATE / "logs"
        self.logs.mkdir(exist_ok=True)
        self.shots = Path(args.shots).expanduser().resolve() if args.shots else STATE / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ small helpers

    def say(self, text: str = "") -> None:
        print(text, flush=True)

    def head(self, text: str) -> None:
        self.say(f"\n== {text}")

    def do(
        self, command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, log: Path | None = None
    ) -> int:
        """Run a command, showing it; in --dry-run only show it. With ``log`` the output goes there, not on screen."""
        self.say("$ " + " ".join(command) + (f"   (in {cwd.relative_to(ROOT)})" if cwd != ROOT else ""))
        if self.args.dry_run:
            return 0
        merged = {**os.environ, **(env or {})}
        if log is None:
            return subprocess.call(command, cwd=cwd, env=merged)
        with log.open("w") as out:
            return subprocess.call(command, cwd=cwd, env=merged, stdout=out, stderr=subprocess.STDOUT)

    def browsers(self) -> list[str]:
        return ["chromium", "firefox"] if self.args.browser == "both" else [self.args.browser]

    # ------------------------------------------------------------------ setup

    def setup(self) -> None:
        self.head("Setup (skips what is already done)")
        self._tools()
        self._packages(WEB)
        self._packages(CLIENT)
        self._web_build()
        self._browsers()
        self._assets()
        self.say("Setup done." if not self.args.dry_run else "Dry run: nothing was changed.")

    def _tools(self) -> None:
        for tool, how in (
            ("node", "https://nodejs.org/ or `nvm install 22`, or `brew install node`"),
            ("npm", "it comes with node"),
        ):
            if not shutil.which(tool):
                raise Failure(f"{tool} is not installed ({how}).")
        major = int(subprocess.check_output(["node", "--version"], text=True).strip().lstrip("v").split(".")[0])
        if major < NODE_MAJOR:
            raise Failure(
                f"node {major} is too old; CI uses {NODE_MAJOR}. Use `nvm install {NODE_MAJOR}` or `brew upgrade node`."
            )
        self.say(f"tools: uv, node {major}, npm are there; python packages come from uv.lock (uv run installed them)")

    def _packages(self, folder: Path) -> None:
        """`npm ci` in a folder when its node_modules is missing or its package-lock.json changed."""
        where = folder.relative_to(ROOT).as_posix()
        stamp = folder / "node_modules" / ".e2e-lock-hash"
        digest = hashlib.sha256((folder / "package-lock.json").read_bytes()).hexdigest()
        if stamp.is_file() and stamp.read_text().strip() == digest:
            self.say(f"{where} packages: up to date")
            return
        self.say(f"{where} packages: installing (npm ci)")
        if self.do(["npm", "ci"], cwd=folder):
            raise Failure(f"`npm ci` failed in {where}/.")
        if not self.args.dry_run:
            stamp.write_text(digest)

    def _web_build(self) -> None:
        newest = max((p.stat().st_mtime for p in (WEB / "app").rglob("*") if p.is_file()), default=0.0)
        for extra in ("nuxt.config.ts", "package.json", "package-lock.json"):
            newest = max(newest, (WEB / extra).stat().st_mtime)
        if BUILT.is_file() and BUILT.stat().st_mtime >= newest and not self.args.rebuild:
            self.say("web app: built and up to date")
            return
        self.say("web app: building (npm run build, about a minute)")
        if self.do(["npm", "run", "build"], cwd=WEB):
            raise Failure("`npm run build` failed in web/.")

    def _browsers(self) -> None:
        names = self.browsers()
        # Python's Playwright (tests/e2e and the specs) and Node's (web/e2e) have their own versions and caches.
        self.say(f"browsers: {', '.join(names)} for Python's and for Node's Playwright (quick when already there)")
        for label, command, cwd in (
            ("Python's", [sys.executable, "-m", "playwright", "install", *names], ROOT),
            ("Node's", ["npx", "playwright", "install", *names], WEB),
        ):
            log = self.logs / f"install-browsers-{label[:-2].lower()}.log"
            if self.do(command, cwd=cwd, log=log):
                # Not fatal: a browser may be there already (or $CLAUDIA_CHROMIUM names one). The tests say if not.
                self.say(
                    f"   could not install the browsers for {label} Playwright (offline? behind a proxy?)."
                    f" Last lines of {log.relative_to(ROOT)}:"
                )
                for line in log.read_text(errors="replace").splitlines()[-4:]:
                    self.say("   | " + line)
                self._stop_on_ci(f"the browsers for {label} Playwright are not installed")
        if sys.platform.startswith("linux"):
            self.say(
                "   On Linux a browser may still fail to start for want of system libraries. If it does, run once:"
            )
            self.say(f"   sudo {sys.executable} -m playwright install-deps {' '.join(names)}")

    def _stop_on_ci(self, what: str) -> None:
        """On a computer a missing browser or font costs only some tests, and the run says which. On CI (``$CI`` is set)
        it is a broken setup: skipped tests must not make a green job, so the run stops (D1452)."""
        if os.environ.get("CI") and not self.args.dry_run:
            raise Failure(f"{what}; on CI that stops the run.")

    def _assets(self) -> None:
        for name, module in (
            ("fonts", ["-m", "claudia_fonts", "fetch"]),
            ("hyphenation", ["-m", "claudia_server.hyphenation", "fetch"]),
        ):
            target = STATE / name
            if target.is_dir() and any(target.iterdir()):
                self.say(f"{name}: already fetched")
                continue
            self.say(f"{name}: fetching (the print tests need them)")
            if self.do([sys.executable, *module, str(target)]):
                self.say(f"   could not fetch {name} (offline?). Everything but the print tests will still run.")
                self._stop_on_ci(f"the {name} could not be fetched")

    # ------------------------------------------------------------------ servers

    def _free(self, port: int) -> bool:
        """Free if a server could listen on it now. Like the server, the probe may reuse a port whose old connections
        still wait in TIME_WAIT (PROC-51); Windows allows that without being asked, and there the option would let
        the probe share a port someone listens on."""
        with closing(socket.socket()) as probe:
            if os.name != "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    def _need_ports(self, ports: list[int]) -> None:
        busy = [p for p in ports if not self._free(p)]
        if busy:
            raise Failure(
                f"port {', '.join(map(str, busy))} is in use."
                " Stop the ./start.sh (or other server) that is running, then try again."
            )

    @contextmanager
    def servers(self) -> Iterator[None]:
        """The three one-app servers on 8765-8767, as CI starts them, with temporary document folders."""
        self._need_ports(list(PORTS.values()))
        work = Path(tempfile.mkdtemp(prefix="claudia-e2e-", dir=STATE))
        processes: list[subprocess.Popen] = []
        try:
            for app, port in PORTS.items():
                command = [
                    sys.executable,
                    "-m",
                    "claudia_server",
                    "--no-tls",
                    "--port",
                    str(port),
                    "--model",
                    MODELS[app],
                    "--web",
                    str(WEB / ".output" / "public"),
                    "--dir",
                    str(work / f"documents-{port}"),
                    "--state-dir",
                    str(work / f"state-{port}"),
                ]
                for flag, name in (("--fonts", "fonts"), ("--hyphenation", "hyphenation")):
                    if (STATE / name).is_dir() and any((STATE / name).iterdir()):
                        command += [flag, str(STATE / name)]
                self.say("$ " + " ".join(command[:6]) + " ...")
                if not self.args.dry_run:
                    processes.append(
                        subprocess.Popen(
                            command,
                            cwd=ROOT,
                            stdout=(self.logs / f"server-{port}.log").open("w"),
                            stderr=subprocess.STDOUT,
                        )
                    )
            if not self.args.dry_run:
                self._wait_for(list(PORTS.values()), processes)
            yield
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(10)
                except subprocess.TimeoutExpired:
                    process.kill()
            shutil.rmtree(work, ignore_errors=True)

    def _wait_for(self, ports: list[int], processes: list[subprocess.Popen]) -> None:
        import urllib.request

        deadline = time.monotonic() + START_SECONDS
        pending = set(ports)
        while pending and time.monotonic() < deadline:
            for process in processes:
                if process.poll() is not None:
                    raise Failure(f"a server stopped while starting; see {self.logs}/server-*.log")
            for port in sorted(pending):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1).read()
                    pending.discard(port)
                except OSError:
                    pass
            time.sleep(0.5)
        if pending:
            raise Failure(
                f"the servers on {sorted(pending)} did not answer within {START_SECONDS} s;"
                f" see {self.logs}/server-*.log"
            )

    # ------------------------------------------------------------------ what to run

    def _record(self, name: str, command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> bool:
        """Run one command as one result of the summary; whether it passed (a dry run passes)."""
        log = self.logs / f"{name}.log"
        started = time.monotonic()
        code = self.do(command, cwd=cwd, env={"SHOTS": str(self.shots), **(env or {})}, log=log)
        seconds = time.monotonic() - started
        if self.args.dry_run:
            return True
        self.results.append(Result(name, code == 0, seconds))
        if code:
            lines = log.read_text(errors="replace").splitlines()
            failed = [line for line in lines if line.startswith(("FAILED ", "ERROR "))]  # pytest's summary (PROC-52)
            self.say(f"   FAILED ({seconds:.0f} s).")
            for line in failed:
                self.say("   | " + line)
            self.say(f"   Last lines of {log.relative_to(ROOT)}:")
            for line in lines[-20:]:
                self.say("   | " + line)
        else:
            lines = [line for line in log.read_text(errors="replace").splitlines() if line.strip()]
            summary = lines[-1].strip(" =") if lines and "pytest" in command[-3:] + command[:3] else ""
            note = f": {summary}" if summary else ""
            self.results[-1].note = "skipped some" if "skipped" in summary else ""
            self.say(f"   ok ({seconds:.0f} s){note}")
        return code == 0

    def regression(self) -> None:
        only = set(self.args.only or [])
        unknown = only - {script.name for script in SCRIPTS} - {"pytest"}
        if unknown:
            known = sorted(script.name for script in SCRIPTS)
            raise Failure(f"no such script: {', '.join(sorted(unknown))}. Known: pytest, {', '.join(known)}")
        chosen = [script for script in SCRIPTS if not only or script.name in only]

        if not only or "pytest" in only:
            self.head("tests/e2e, with the specs (real servers, one Chromium)")
            self._record("pytest-e2e", pytest_command("tests/e2e"))

        shared = [script for script in chosen if script.runs in SHARED]
        if shared:
            self.head("web/e2e scripts against the three servers (ports 8765-8767)")
            with self.servers():
                for script in shared:
                    env = {} if script.runs == "all" else {"URL": f"http://127.0.0.1:{PORTS[script.runs]}/"}
                    if script.name == "redaction":
                        env["TEXT_URL"] = f"http://127.0.0.1:{PORTS['composes']}/"
                    self._npm(script, env)

        own = [script for script in chosen if script.runs == OWN]
        if own:
            self.head("web/e2e scripts that start a server of their own")
            self._need_ports([8766])
            for script in own:
                self._npm(script)

        for script in chosen:
            if script.runs == FONTS:
                self.head("Server settings > Fonts (a server of its own on port 8768)")
                self._admin_fonts(script)
            elif script.runs in CLIENT_WINDOWS:
                self.head(f"{WHERE[script.runs]} (shell page, core, server and web app; Neutralino faked)")
                self._client_window(script)

    def _npm(self, script: Script, env: dict[str, str] | None = None) -> None:
        self._record(f"e2e-{script.name}", ["npm", "run", "--silent", script.npm], cwd=WEB, env=env)

    def _client_window(self, script: Script) -> None:
        """A build behaves like its platform wherever it runs (D660), so both windows are tested on any computer."""
        if self._record(f"build-{script.runs}", ["npm", "run", "--silent", f"build:{script.runs}"], cwd=CLIENT):
            self._npm(script)

    def _admin_fonts(self, script: Script) -> None:
        self._need_ports([8768])
        work = Path(tempfile.mkdtemp(prefix="claudia-e2e-fonts-", dir=STATE))
        process = None
        try:
            if self.do([sys.executable, "scripts/make_admin_fonts_sample.py", str(work / "house-fonts")]):
                raise Failure("could not make the sample fonts.")
            if self.args.dry_run:
                return
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "claudia_server",
                    "--no-tls",
                    "--port",
                    "8768",
                    "--web",
                    str(WEB / ".output" / "public"),
                    "--dir",
                    str(work / "documents"),
                    "--state-dir",
                    str(work / "state"),
                ],
                cwd=ROOT,
                stdout=(self.logs / "server-8768.log").open("w"),
                stderr=subprocess.STDOUT,
            )
            self._wait_for([8768], [process])
            code = work / "state" / "admin" / "setup-code"  # the server's setup code, for naming its administrator
            self._npm(
                script,
                {
                    "URL": "http://127.0.0.1:8768/",
                    "FONTS": str(work / "house-fonts"),
                    "SETUP_CODE": code.read_text(encoding="utf-8").strip() if code.is_file() else "",
                },
            )
        finally:
            if process:
                process.terminate()
                process.wait(10)
            shutil.rmtree(work, ignore_errors=True)

    def specs(self, level: str) -> None:
        self.head(f"specs ({level})")
        marker = "core" if level == "core" else "core or extended"
        command = [sys.executable, "-m", "pytest", "tests/e2e/specs", "-m", marker]
        if self.args.feature:
            command += ["-k", self.args.feature]
        env = {
            "CLAUDIA_E2E_BROWSER": self.args.browser,
            "CLAUDIA_E2E_SHOTS": str(self.shots),
            "CLAUDIA_E2E_FONTS": str(STATE / "fonts"),
        }
        if self.args.headed:
            env["CLAUDIA_E2E_HEADED"] = "1"
        self._record(f"specs-{level}", command, env=env)

    def summary(self) -> int:
        if not self.results:
            return 0
        self.head("Summary")
        for result in self.results:
            flag = "ok    " if result.ok else "FAILED"
            self.say(
                f"  {flag}  {result.name:<28} {result.seconds:5.0f} s"
                f"  {'(some tests were skipped: see its log)' if result.note else ''}"
            )
        failed = [r for r in self.results if not r.ok]
        self.say(
            f"\n{len(self.results) - len(failed)} passed, {len(failed)} failed."
            f" Screenshots: {self.shots}   Logs: {self.logs}"
        )
        return 1 if failed else 0


WHERE = {
    "computes": "against the computes server",
    "composes": "against the composes server",
    "creates": "against the creates server",
    "all": "against all three servers",
    OWN: "starts a server of its own",
    FONTS: "starts a server of its own, with sample house fonts",
    "windows": "The Windows client's window, built first",
    "macos": "The macOS client's window, built first",
}


def listing() -> None:
    print("regression (what CI runs; needs the web app built; minutes are rough, CI takes about 15 in all)")
    pytest_runs = "the three servers, the grid, documents between servers, names; the specs"
    print(f"  {'pytest tests/e2e':<18} {pytest_runs:<52} ~8 min")
    for script in SCRIPTS:
        print(f"  {script.name:<18} {WHERE[script.runs]:<52} ~{script.minutes} min")
    print("\nspecs (claudiaoffice-log/specs, step code in tests/e2e/specs), counted from the files just now:")
    collected = subprocess.run(
        # -qq prints one "file: count" line per test file; addopts is emptied so that a -q there does not change it
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-qq",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            str(SPECS_TESTS),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if collected.returncode:
        print("  could not collect them; run `uv run pytest --collect-only tests/e2e/specs` to see why")
        return
    per_file = {
        path.rsplit("/", 1)[-1]: int(count)
        for path, _, count in (line.rpartition(": ") for line in collected.stdout.splitlines())
        if path.endswith(".py") and count.isdigit()
    }
    for name, count in sorted(per_file.items()):
        print(f"  {name:<32} {count:>4} scenarios")
    print(f"  {sum(per_file.values())} scenarios in all. Which of them skip, and why, every run says at its end.")
    print("  Spec files no test runs yet are listed in tests/test_specs_are_bound.py (NOT_BOUND_YET).")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="./run-e2e.sh",
        description=__doc__.split("\n\n")[0],
        epilog=__doc__.split("\n\n", 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "what",
        nargs="?",
        default="core",
        choices=["setup", "core", "extended", "specs", "regression", "all"],
        help="what to run (default: core); see below",
    )
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "both"],
        default="chromium",
        help="for the specs and for setup (default: chromium)",
    )
    parser.add_argument("--feature", metavar="TEXT", help="specs only: run the spec files whose name contains TEXT")
    parser.add_argument(
        "--only", action="append", metavar="NAME", help="regression only: run only this script (repeatable)"
    )
    parser.add_argument("--headed", action="store_true", help="specs only: show the browser window")
    parser.add_argument("--shots", metavar="DIR", help="where the screenshots go (default .claudia/e2e/shots)")
    parser.add_argument("--no-setup", action="store_true", help="do not set anything up first")
    parser.add_argument("--rebuild", action="store_true", help="build the web app again, even if it looks up to date")
    parser.add_argument("--dry-run", action="store_true", help="show the commands, run and change nothing")
    parser.add_argument("--list", action="store_true", help="list what there is to run and exit")
    args = parser.parse_args()

    if args.list:
        listing()
        return 0
    runner = Runner(args)
    try:
        if not args.no_setup or args.what == "setup":
            runner.setup()
        if args.what in ("regression", "all"):
            runner.regression()
        if args.what in ("core",):
            runner.specs("core")
        if args.what in ("extended", "specs", "all"):
            runner.specs("extended")
    except Failure as problem:
        print(f"\n{problem}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())
