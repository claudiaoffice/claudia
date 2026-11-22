// The one way a script of web/e2e starts its browser (PROC-52, D1453).
//
// Chromium is Playwright's own, or the one $CLAUDIA_CHROMIUM names: a browser already on this computer, for a computer
// that cannot download Playwright's (the same variable the Python tests read). BROWSER=firefox starts Firefox instead;
// most scripts are only run in Chromium (PROC-47).
const { chromium, firefox } = require('playwright')

/** The browser this run asks for, started. */
function launch() {
  if (process.env.BROWSER === 'firefox') return firefox.launch()
  const own = process.env.CLAUDIA_CHROMIUM
  return chromium.launch(own ? { executablePath: own } : {})
}

module.exports = { launch }
