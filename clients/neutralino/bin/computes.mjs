#!/usr/bin/env node
// `claudia-computes`: the command npm links from package.json's `bin` (on Windows as `claudia-computes.cmd`). The same
// program as `node dist\launch.js computes`, with the same arguments as the Linux and macOS clients: [--server URL] [--debug].
import { main } from '../dist/launch.js'

process.exitCode = await main(['computes', ...process.argv.slice(2)])
