# Specs

The scenarios the owner reviews before a feature is coded, and the ones every bug fix starts with (a failing scenario
first). One file per feature, in Gherkin (`Feature`, `Scenario`, `Given/When/Then`), in plain language.

* **`@core`**: the behaviours a person would stop using the product over; they run in CI on every push.
* **`@extended`**: the rest of what the feature promises; they run in the nightly job and before delivery.
* **`@app:computes`, `@app:composes`, `@app:creates`**: the apps a scenario runs in; none means all three.
* **`@e2e:<file>`**: where the browser test is (`web/e2e/`), or `@unit:<path>` / `@io:<path>` where the scenario is
  tested by a unit or a file-format test because no browser is needed.

A scenario that is not built yet says `@pending:<decision>`; the test behind it is written, gated, and the gate goes with
the feature.
