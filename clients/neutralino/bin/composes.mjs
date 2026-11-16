#!/usr/bin/env node
// `claudia-composes`: the command npm links from package.json's `bin` (on Windows as `claudia-composes.cmd`). The same
// program as `node dist\launch.js composes`, with the same arguments as the Linux and macOS clients: [--server URL] [--debug].
import { main } from '../dist/launch.js'

process.exitCode = await main(['composes', ...process.argv.slice(2)])
