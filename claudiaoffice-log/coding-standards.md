1. **Automated formatting and linting through ruff mypy and vulture**

   
2. **Tests are part of the definition of done, written with the code.** Follow a test pyramid: many fast unit tests, fewer integration tests, and a thin layer of end-to-end tests for the critical user journeys. Every implementation starts with tests that check the acceptance criteria and every bug fix starts with a failing test that reproduces it. Tests must be deterministic.
   
3. **Modules have explicit boundaries and a small public surface.** Dependencies point in one direction, there are no cycles, and internals are private by default. 
   
4. **Public interfaces are versioned and documented, and breaking changes are deliberate.** This covers APIs, file formats, and wire protocols. Use semantic versioning and a deprecation policy (announce, warn, then remove). Generate the reference documentation from the code so it can’t drift.
   
5. **Write code to be read, with small functions and honest names.** Each function does one thing, names use the domain’s vocabulary, and comments explain why rather than what. We keep a shared glossary of domain terms in glossary.md and use them consistently in code, tests, and UI. 
   
6. **Handle errors explicitly and consistently.** Define one error-handling strategy (typed errors or exceptions, whichever fits the language) and one rule for what gets retried or surfaced. Never swallow errors silently, and validate at system boundaries. Log structured events with correlation IDs, so you can debug production from the logs alone.
   
7. **Treat security and dependencies as a standing practice.** Never commit secrets, and validate and sanitize all external input. Pin and lock dependencies, scan them automatically, and keep a bar for adding new ones, since every dependency is code you now maintain. Review the license of each dependency at the time it is added.
   
8. **We record architectural decisions and the reasoning behind them.** we keep short, dated decision records (ADRs) in the repo next to the code. In a large project the question “why did we do it this way?” comes up constantly. Every decision is a file in claudiaoffice-log/decision-log
   
9. **Pay down technical debt continuously and measure it.** Track complexity, duplication, dead code, build time, and test runtime, and fail the build when the numbers regress past agreed thresholds. Reserve a fixed slice of every cycle for refactoring. Debt that goes unmeasured grows, and a large project can quietly lose half its velocity before anyone notices.
