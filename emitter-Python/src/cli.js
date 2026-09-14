#!/usr/bin/env node
'use strict'

const fs = require('fs')
const path = require('path')
const { PythonEmitter } = require('./python-emitter')

function usage() {
  console.error('Usage: uast2py --input <uast.json> --output <source.py> [--report <fidelity.json>]')
  process.exit(2)
}

const args = process.argv.slice(2)
function value(flag) {
  const index = args.indexOf(flag)
  return index >= 0 ? args[index + 1] : undefined
}
const input = value('--input')
const output = value('--output')
const report = value('--report')
if (!input || !output) usage()

const uast = JSON.parse(fs.readFileSync(input, 'utf8'))
const result = new PythonEmitter().emit(uast)
fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true })
fs.writeFileSync(output, result.source, 'utf8')
if (report) {
  fs.mkdirSync(path.dirname(path.resolve(report)), { recursive: true })
  fs.writeFileSync(report, `${JSON.stringify(result.report, null, 2)}\n`, 'utf8')
}
