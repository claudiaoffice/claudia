# Versioning policy

Claudia has three kinds of public interface. Each has its own version and its own place where changes are recorded.

| Interface | Where it is defined | Version | Record of changes |
|---|---|---|---|
| Python API of a package (`claudia_core`, `claudia_server`, `claudia_client`, ...) | `__all__` in the package's `__init__.py` | `__version__` in `_version.py`, semantic versioning | the package's `CHANGELOG.md`, and a snapshot test (`tests/api/<package>.json`) |
| Network API (E3) | the protocol module of `claudia-server` | `PROTOCOL_VERSION` (now 1), named in `/api/protocol` | the server page of the documentation |
| Document format (log, commands) | command `schema` numbers, `Manifest.format` | per command kind; upcasters bring old data up to date | `CHANGELOG.md` and the upcaster tests with fixture logs |

## Python API

* Only what is listed in `__all__` is public. Everything else (names with `_`, other modules' contents) may change in any release.
* **Patch** (0.3.x): no change to the API surface.
* **Minor** (0.x.0): additions. While the major version is 0, a minor release may also break the API; the changelog says **Breaking**.
* **Major** (x.0.0, from 1.0): breaking changes. Deprecate first: the old name keeps working for one minor version and raises a `DeprecationWarning`.
* The snapshot test fails on any change to a public name or signature. To pass it you raise the version, write the changelog entry and regenerate the snapshot (`uv run python scripts/api_surface.py --write`), so a reviewer sees the API change as a diff.
* Every public class and function needs a docstring: the API reference is generated from them.

## Documents are forever

A document written by version N must open in every later version. A command whose data changes gets a new `schema` and an upcaster that is tested with a fixture log of the old schema. Opening a document written by a *newer* version fails with a clear message (`SchemaTooNew`); nothing is guessed.
