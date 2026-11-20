---
id: D1376
title: "--admin with a password file names the first administrator at start, and never changes one that exists"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1376 · --admin with a password file names the first administrator at start, and never changes one that exists

**Decided 2026-11-20** by the owner (SEC-12's optional part, now in scope; mock-up panel 7).

- `--admin NAME` (or `CLAUDIA_ADMIN`) with `--admin-password-file FILE` (or `CLAUDIA_ADMIN_PASSWORD_FILE`) names
  NAME the first administrator at start, with the password in FILE (its first line; the rules of an administrator's
  password apply). For deployments where nobody reads the log: the demo, which starts afresh on every cold start, and
  containers. The password is never taken from the command line or from an environment value of its own, which other
  processes and logs can see.
- **Only when nobody is named.** With administrators already there it changes nothing and says so in the banner (also
  when NAME is one of them: a changed password file does not change a password; that is what signing in and *Change
  password* are for). With `--reset-administrators` in the same start it names the new first one.
- The container's entry point (`docker/entrypoint.sh`) turns `CLAUDIA_ADMIN` and `CLAUDIA_ADMIN_PASSWORD` (as a
  platform's secret variables give them) into a private file and these options, and removes the variable before the
  server starts. Setting them on the demo is the owner's step in Scaleway.
