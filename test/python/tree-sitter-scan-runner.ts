// Isolated processes avoid analyzer caches leaking between migration comparisons.
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const Parser = require('../../src/engine/parser/parser')
const Core = require('../../src/engine/parser/parser-core')
const { execute } = require('../../src/interface/starter')
const { recordFindingStr } = require('../test-utils')

function* walkPyFiles(dir: string): Generator<string> {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) yield* walkPyFiles(full)
    else if (entry.isFile() && entry.name.endsWith('.py')) yield full
  }
}

if (process.argv[2] === 'legacy') {
  Parser.parseProject = async (dir: string, options: any) => {
    const files = Array.from(walkPyFiles(dir)).sort()
    const sources = files.map(f => fs.readFileSync(f, 'utf8'))
    const oracle = path.resolve(__dirname, '../../../uast/parser-Python/tests/legacy.py')
    const result = spawnSync(process.env.PYTHON_UAST_ORACLE!, [oracle, '--batch', '--unit'], {
      input: JSON.stringify(sources), encoding: 'utf8', maxBuffer: 32 * 1024 * 1024,
    })
    if (result.status !== 0) throw new Error(result.stderr || String(result.error))
    const units = JSON.parse(result.stdout)
    const asts: Record<string, any> = {}, sourceMap: Record<string, string> = {}
    files.forEach((file, i) => {
      if (units[i].error) throw new Error(units[i].error)
      const ast = units[i].body
      const relocate = (node: any) => {
        if (!node || typeof node !== 'object') return
        if (node.loc?.sourcefile === 'fixture.py') node.loc.sourcefile = file
        Object.values(node).forEach(relocate)
      }
      relocate(ast)
      asts[file] = ast
      sourceMap[file] = sources[i]
    })
    Core.processProjectAst(asts, { unit: 'file', needsSourcefile: true }, options, sourceMap)
    return asts
  }
}

async function main() {
  const targetDir = process.argv[3] || path.resolve(__dirname, 'no-init-dispatch-cases')
  const recorder = recordFindingStr()
  recorder.clearResult()
  await execute(null, [
    targetDir,
    '--ruleConfigFile', path.resolve(__dirname, 'rule_config_xast_python3.json'),
    '--analyzer', 'PythonAnalyzer', '--checkerIds', 'taint_flow_test',
  ], recorder.printAndAppend)
  console.log('YASA_MIGRATION_RESULT=' + JSON.stringify(recorder.getFormatResult()))
}
main().catch(error => { console.error(error); process.exitCode = 1 })
