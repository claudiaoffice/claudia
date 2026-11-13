#!/usr/bin/env node
// `claudia-creates`: the command npm links from package.json's `bin` (on Windows as `claudia-creates.cmd`). The same
// program as `node dist\launch.js creates`, with the same arguments as the Linux and macOS clients: [--server URL] [--debug].
import { main } from '../dist/launch.js'

process.exitCode = await main(['creates', ...process.argv.slice(2)])
