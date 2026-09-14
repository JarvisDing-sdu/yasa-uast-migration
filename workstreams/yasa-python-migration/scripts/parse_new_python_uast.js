#!/usr/bin/env node
'use strict'

/**
 * Test-only CLI: parse one Python file using the in-process Tree-sitter parser
 * and serialize its CompileUnit UAST. Production Engine passes this object in
 * memory; this command exists solely for old/new regression evidence.
 */
const { mkdirSync, readFileSync, writeFileSync } = require('node:fs')
const { dirname, resolve } = require('node:path')
const { Parser } = require('../../../uast/parser-Python')

function usage() {
  console.error('Usage: node parse_new_python_uast.js --input <source.py> --output <uast.json>')
  process.exit(2)
}

function value(args, flag) {
  const index = args.indexOf(flag)
  return index >= 0 ? args[index + 1] : undefined
}

async function main() {
  const args = process.argv.slice(2)
  const input = value(args, '--input')
  const output = value(args, '--output')
  if (!input || !output) usage()

  const inputPath = resolve(input)
  const outputPath = resolve(output)
  const parser = new Parser({ sourcefile: inputPath })
  await parser.init()
  const uast = parser.parse(readFileSync(inputPath, 'utf8'), { sourcefile: inputPath })
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, `${JSON.stringify(uast, null, 2)}\n`, 'utf8')
}

main().catch((error) => {
  console.error(error && (error.stack || error.message) || String(error))
  process.exitCode = 1
})
