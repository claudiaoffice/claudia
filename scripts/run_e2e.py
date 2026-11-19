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
    regression  what CI runs today: pytest tests/e2e, and the Node scripts in web/e2e against real servers.
                These scripts only drive Chromium; --browser does not change that.
    all         regression, then specs.
    setup       only the setup below.

The specs (claudiaoffice-log/specs/*.feature) are written and under review; their step code is not built yet, so
"core" and "extended" say so and stop until tests/e2e/specs exists. "regression" works today.

What setup does (every run does it first, and skips what is already done; --no-setup skips all of it)
    1. checks that uv, node (22 or newer) and npm are installed, and says how to get them if not;
    2. python packages: `uv run` already installed them from uv.lock before this script started;
    3. web packages: `npm ci` in web/ when node_modules is missing or package-lock.json changed;
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

# The Node scripts of web/e2e, as CI runs them (.github/workflows/ci.yml, "Two people in each app"): which app's
# server each talks to. `name` is the npm script e2e:<name>; "e2e" alone is demo.cjs. Minutes are rough.
WITH_SERVERS: list[tuple[str, str, int]] = [
    ("demo", "computes", 1),
    ("pointing", "computes", 1),
    ("regions", "computes", 1),
    ("grid-a11y", "computes", 1),
    ("describe", "computes", 1),
    ("redaction", "computes", 1),
    ("composes", "composes", 1),
    ("composes-wrap", "composes", 1),
    ("styling", "composes", 1),
    ("style-delete", "composes", 1),
    ("print", "composes", 2),
    ("lists", "composes", 1),
    ("dock-text", "composes", 1),
    ("slides", "creates", 1),
    ("creates-styles", "creates", 1),
    ("print-creates", "creates", 2),
    ("describe-creates", "creates", 1),
    ("present", "creates", 1),
    ("dock", "creates", 1),
    ("keys", "all", 1),
]
# These start (and restart) a server of their own, so the shared servers must be stopped first.
OWN_SERVER = ["resilience", "recovery", "search", "pivots", "passwords", "details"]
# One more with a server of its own and a folder of house fonts (CI step "Server settings > Fonts").
FONTS_ADMIN = "admin-fonts"


class Failure(Exception):
    """Something the person has to fix before going on; the message says what and how."""


@dataclass
class Result:
    name: str
    ok: bool
    seconds: float
    note: str = ""


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
        self._web_packages()
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

    def _web_packages(self) -> None:
        lock = WEB / "package-lock.json"
        stamp = WEB / "node_modules" / ".e2e-lock-hash"
        digest = hashlib.sha256(lock.read_bytes()).hexdigest()
        if stamp.is_file() and stamp.read_text().strip() == digest:
            self.say("web packages: up to date")
            return
        self.say("web packages: installing (npm ci)")
        if self.do(["npm", "ci"], cwd=WEB):
            raise Failure("`npm ci` failed in web/.")
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
        if sys.platform.startswith("linux"):
            self.say(
                "   On Linux a browser may still fail to start for want of system libraries. If it does, run once:"
            )
            self.say(f"   sudo {sys.executable} -m playwright install-deps {' '.join(names)}")

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

    # ------------------------------------------------------------------ servers

    def _free(self, port: int) -> bool:
        with closing(socket.socket()) as probe:
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

    def _record(self, name: str, command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
        log = self.logs / f"{name}.log"
        started = time.monotonic()
        code = self.do(command, cwd=cwd, env={"SHOTS": str(self.shots), **(env or {})}, log=log)
        seconds = time.monotonic() - started
        if self.args.dry_run:
            return
        self.results.append(Result(name, code == 0, seconds))
        if code:
            self.say(f"   FAILED ({seconds:.0f} s). Last lines of {log.relative_to(ROOT)}:")
            for line in log.read_text(errors="replace").splitlines()[-20:]:
                self.say("   | " + line)
        else:
            lines = [line for line in log.read_text(errors="replace").splitlines() if line.strip()]
            summary = lines[-1].strip(" =") if lines and "pytest" in command[-3:] + command[:3] else ""
            note = f": {summary}" if summary else ""
            self.results[-1].note = "skipped some" if "skipped" in summary else ""
            self.say(f"   ok ({seconds:.0f} s){note}")

    def regression(self) -> None:
        only = set(self.args.only or [])
        known = {n for n, _, _ in WITH_SERVERS} | set(OWN_SERVER) | {FONTS_ADMIN, "pytest"}
        unknown = only - known
        if unknown:
            raise Failure(f"no such script: {', '.join(sorted(unknown))}. Known: {', '.join(sorted(known))}")
        want = lambda name: not only or name in only  # noqa: E731

        self.head("tests/e2e (real servers, one Chromium)")
        if want("pytest"):
            self._record("pytest-e2e", [sys.executable, "-m", "pytest", "-rs", "tests/e2e"])

        chosen = [row for row in WITH_SERVERS if want(row[0])]
        if chosen:
            self.head("web/e2e scripts against the three servers (ports 8765-8767)")
            with self.servers():
                for name, app, _ in chosen:
                    env = {} if app == "all" else {"URL": f"http://127.0.0.1:{PORTS[app]}/"}
                    if name == "redaction":
                        env["TEXT_URL"] = f"http://127.0.0.1:{PORTS['composes']}/"
                    self._record(
                        f"e2e-{name}",
                        ["npm", "run", "--silent", "e2e" if name == "demo" else f"e2e:{name}"],
                        cwd=WEB,
                        env=env,
                    )

        own = [n for n in OWN_SERVER if want(n)]
        if own:
            self.head("web/e2e scripts that start a server of their own")
            self._need_ports([8766])
            for name in own:
                self._record(f"e2e-{name}", ["npm", "run", "--silent", f"e2e:{name}"], cwd=WEB)

        if want(FONTS_ADMIN):
            self.head("Server settings > Fonts (a server of its own on port 8768)")
            self._admin_fonts()

    def _admin_fonts(self) -> None:
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
            self._record(
                "e2e-admin-fonts",
                ["npm", "run", "--silent", "e2e:admin-fonts"],
                cwd=WEB,
                env={"URL": "http://127.0.0.1:8768/", "FONTS": str(work / "house-fonts")},
            )
        finally:
            if process:
                process.terminate()
                process.wait(10)
            shutil.rmtree(work, ignore_errors=True)

    def specs(self, level: str) -> None:
        self.head(f"specs ({level})")
        if not SPECS_TESTS.is_dir():
            self.say("The specs are written (claudiaoffice-log/specs/*.feature) but their step code is not built yet:")
            self.say("tests/e2e/specs does not exist. Nothing to run here yet.")
            return
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


def listing() -> None:
    print("regression (works today; needs the web app built; about 25-35 minutes in all)")
    print("  pytest tests/e2e (three servers greeting, grid, documents between servers, names)")
    for name, app, minutes in WITH_SERVERS:
        print(f"  {name:<18} against the {app} server{'s' if app == 'all' else '':<2}  ~{minutes} min")
    for name in OWN_SERVER:
        print(f"  {name:<18} starts a server of its own")
    print(f"  {FONTS_ADMIN:<18} starts a server of its own, with sample house fonts")
    print("\nspecs (written, under review; step code not built yet)")
    for feature in sorted((ROOT / "claudiaoffice-log" / "specs").rglob("*.feature")):
        print(f"  {feature.relative_to(ROOT / 'claudiaoffice-log' / 'specs')}")


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
