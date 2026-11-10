---
id: D134
title: "The worker-pool abstraction (a generic `submit(fn, *args,"
status: current
applies-to: all
date: 2026-11-06
round: "Worker pool placement (twenty-first round)"
supersedes: []
superseded-by: []
---

# D134 · The worker-pool abstraction (a generic `submit(fn, *args,

**The worker-pool abstraction (a generic `submit(fn, *args, **kwargs)` over a `ProcessPoolExecutor`, bridged into `asyncio`, with crash isolation if a worker process dies outright) lives in `claudia-server`, not `claudia-core`, and each server process owns exactly one instance of it, started and stopped with its `Hub`.**

**Notes.** Owner's opening framing ("in the core, so it can be re-used in any of the three apps") turned out to rest on a wrong premise, corrected while reading `cli.py`: `make_plan()` starts exactly one `Hub` per OS process, for exactly one `--model` (one app type). There is no single running `claudia-server` process that already hosts composes, computes and creates together — the real topology is one process per app type. So reuse across apps was never going to come from a shared running instance anyway; it comes from the abstraction being available to every process that is a `claudia-server` process, which all three already are. `claudia-core` stays dependency-free and I/O-free (`pyproject.toml: dependencies = []`) — `asyncio`, `ProcessPoolExecutor` and process lifecycle do not belong in the pure kernel. Each process owning its own pool (over one pool shared across processes) was agreed directly: a document-hosting process must be able to start, stop and recover its pool without coordinating with any other process. Built in `packages/claudia-server/src/claudia_server/workers.py` (`WorkerPool`, `DEFAULT_WORKERS`), wired as `Hub.workers`.
