import assert from 'assert'
import path from 'path'
import { spawnSync } from 'node:child_process'
import { before, describe, it } from 'mocha'

const PythonBuilder = require('../../src/engine/parser/python/python-ast-builder')
const UnifiedParser = require('../../src/engine/parser/parser')
const { readExpectRes, resolveTestFindingResult } = require('../test-utils')

function scan(mode: string): string {
  const result = spawnSync(process.execPath, ['--import', 'tsx', path.join(__dirname, 'tree-sitter-scan-runner.ts'), mode], {
    cwd: path.resolve(__dirname, '../..'), env: process.env, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024,
    timeout: 60000,
  })
  assert.strictEqual(result.status, 0, result.stderr || result.stdout)
  const line = result.stdout.split('\n').find(line => line.startsWith('YASA_MIGRATION_RESULT='))
  assert.ok(line, result.stdout)
  return JSON.parse(line.slice('YASA_MIGRATION_RESULT='.length))
}

describe('Python tree-sitter integration', function () {
  this.timeout(30000)

  before(async function () {
    await Promise.all([PythonBuilder.ensureInitialized(), PythonBuilder.ensureInitialized()])
  })

  it('parses in memory with the original filename and no binary SDK', function () {
    const ast = PythonBuilder.parseSingleFile('result = taint_src\nsink(result)', {
      sourcefile: 'memory.py',
      uastSDKPath: '/missing-legacy-sdk',
    })
    assert.strictEqual(ast.type, 'CompileUnit')
    assert.strictEqual(ast.loc.sourcefile, 'memory.py')
    assert.strictEqual(ast.body[0].right.name, 'taint_src')
    assert.throws(() => PythonBuilder.parseSingleFile('x ='), SyntaxError)
    assert.strictEqual(PythonBuilder.parseSingleFile('x = 1').body[0].right.value, 1)
  })

  it('uses the shared single-file postprocessing and source cache', function () {
    const file = path.resolve('in-memory-python-fixture.py')
    const cache = new Map([[file, ['value = source()', 'sink(value)']]])
    const ast = UnifiedParser.parseSingleFile(file, { language: 'python', sourcefile: file }, cache)
    assert.ok(ast)
    assert.strictEqual(ast.body[0].right.callee.name, 'source')
  })

  let actual: string
  it('preserves historical finding counts per file through the project/worker path', function () {
    actual = scan('new')
    const counts = (text: string) => [...resolveTestFindingResult(text)].map(([key, value]: [string, any]) =>
      [key, Array.isArray(value) ? value.length : value]).sort()
    assert.deepStrictEqual(counts(actual), counts(readExpectRes(path.resolve(__dirname, 'expect/python-no-init-dispatch-expect.result'))))
    assert.match(actual, /#Total-findings:7/)
  })

  ;(process.env.PYTHON_UAST_ORACLE ? it : it.skip)('exactly matches live legacy findings including every trace step', function () {
    this.timeout(90000)
    assert.strictEqual(actual || scan('new'), scan('legacy'))
  })
})
