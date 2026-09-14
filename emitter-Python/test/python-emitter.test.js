'use strict'

const assert = require('assert')
const { PythonEmitter, UnsupportedNodeError } = require('../src/python-emitter')

const meta = { isConstructor: false, isAsync: false, decorators: null, parameterKind: null }
const id = (name) => ({ type: 'Identifier', name, loc: null, _meta: meta })
const lit = (value, literalType) => ({ type: 'Literal', value, literalType, loc: null, _meta: meta })
const unit = (body) => ({ type: 'CompileUnit', language: 'python', body, loc: null, _meta: meta })

const emitter = new PythonEmitter()
const input = unit([{ type: 'AssignmentExpression', left: id('x'), right: lit(1, 'number'), operator: '=', loc: null, _meta: meta }])
const first = emitter.emit(input)
const second = emitter.emit(input)
assert.strictEqual(first.source, 'x = 1\n')
assert.strictEqual(first.source, second.source)
assert.deepStrictEqual(first.report.losses, [])
assert.deepStrictEqual(first.report.nodeCounts, {
  CompileUnit: 1,
  AssignmentExpression: 1,
  Identifier: 1,
  Literal: 1,
})

const dynamic = { type: 'DynamicType', id: null, loc: null, _meta: meta }
const selfDeclaration = {
  type: 'VariableDeclaration', id: id('self'), init: { type: 'ThisExpression', loc: null, _meta: meta },
  varType: dynamic, loc: null, _meta: meta,
}
const method = {
  type: 'FunctionDefinition', id: id('get'), parameters: [], returnType: null, modifiers: [],
  body: {
    type: 'ScopedStatement', loc: null, _meta: meta,
    body: [selfDeclaration, {
      type: 'ReturnStatement', isYield: false, loc: null, _meta: meta,
      argument: { type: 'MemberAccess', object: id('self'), property: id('value'), computed: false, loc: null, _meta: meta },
    }],
  },
  loc: null, _meta: meta,
}
const classResult = emitter.emit(unit([{
  type: 'ClassDefinition', id: id('Box'), supers: [], body: [method], loc: null, _meta: meta,
}]))
assert.strictEqual(classResult.source, 'class Box:\n    def get(self):\n        return self.value\n')

const collections = emitter.emit(unit([
  {
    type: 'AssignmentExpression', operator: '=', left: id('items'), loc: null, _meta: meta,
    right: {
      type: 'ObjectExpression', loc: null, _meta: meta,
      properties: [0, 1].map((value) => ({
        type: 'ObjectProperty', key: lit(value, 'number'), value: lit(value + 1, 'number'), loc: null, _meta: meta,
      })),
    },
  },
  {
    type: 'AssignmentExpression', operator: '=', left: id('mapping'), loc: null, _meta: meta,
    right: {
      type: 'ObjectExpression', loc: null, _meta: meta,
      properties: [{ type: 'ObjectProperty', key: lit('x', 'string'), value: lit(1, 'number'), loc: null, _meta: meta }],
    },
  },
]))
assert.strictEqual(collections.source, 'items = [1, 2]\nmapping = {"x": 1}\n')

const loop = emitter.emit(unit([{
  type: 'RangeStatement', key: null, loc: null, _meta: meta,
  value: {
    type: 'Sequence', loc: null, _meta: meta,
    expressions: [
      { type: 'VariableDeclaration', id: id('left'), init: null, varType: dynamic, loc: null, _meta: meta },
      { type: 'VariableDeclaration', id: id('right'), init: null, varType: dynamic, loc: null, _meta: meta },
    ],
  },
  right: id('pairs'),
  body: { type: 'ScopedStatement', body: [{ type: 'Noop', loc: null, _meta: meta }], loc: null, _meta: meta },
}]))
assert.strictEqual(loop.source, 'for left, right in pairs:\n    pass\n')

const noneLiteral = emitter.emit(unit([{
  type: 'AssignmentExpression', left: id('value'), operator: '=', loc: null, _meta: meta,
  right: { type: 'Literal', value: '...', literalType: null, loc: null, _meta: meta },
}]))
assert.strictEqual(noneLiteral.source, 'value = None\n')

const annotated = emitter.emit(unit([{
  type: 'VariableDeclaration', loc: null, _meta: meta, id: id('dtype'), init: lit('...', null),
  varType: {
    type: 'MemberAccess', object: id('torch'), property: id('dtype'), computed: false, loc: null, _meta: meta,
  },
}]))
assert.strictEqual(annotated.source, 'dtype: torch.dtype = None\n')

const largeInteger = emitter.emit(unit([{
  type: 'AssignmentExpression', left: id('INT64_MAX'), operator: '=', loc: null, _meta: meta,
  right: lit('9223372036854775807', 'number'),
}]))
assert.strictEqual(largeInteger.source, 'INT64_MAX = 9223372036854775807\n')

const bareExcept = emitter.emit(unit([{
  type: 'TryStatement', loc: null, _meta: meta,
  body: { type: 'ScopedStatement', body: [{ type: 'Noop', loc: null, _meta: meta }], loc: null, _meta: meta },
  handlers: [{
    type: 'CatchClause', loc: null, _meta: meta,
    parameter: [{ type: 'VariableDeclaration', loc: null, _meta: meta, init: null, varType: dynamic,
      id: { type: 'Literal', value: null, literalType: 'string', loc: null, _meta: meta } }],
    body: { type: 'ScopedStatement', body: [{ type: 'Noop', loc: null, _meta: meta }], loc: null, _meta: meta },
  }],
  finalizer: { type: 'ScopedStatement', body: [], loc: null, _meta: meta },
}]))
assert.strictEqual(bareExcept.source, 'try:\n    pass\nexcept:\n    pass\n')

const multiSlice = emitter.emit(unit([{
  type: 'AssignmentExpression', left: id('part'), operator: '=', loc: null, _meta: meta,
  right: {
    type: 'MemberAccess', object: id('tensor'), computed: false, loc: null, _meta: meta,
    property: {
      type: 'Sequence', loc: null, _meta: meta,
      expressions: [
        { type: 'SliceExpression', start: null, end: null, step: null, loc: null, _meta: meta },
        { type: 'SliceExpression', start: null, end: null, step: null, loc: null, _meta: meta },
        { type: 'SliceExpression', start: null, end: null, step: null, loc: null, _meta: meta },
        { type: 'SliceExpression', start: null, end: id('limit'), step: null, loc: null, _meta: meta },
      ],
    },
  },
}]))
assert.strictEqual(multiSlice.source, 'part = tensor[:, :, :, :limit]\n')

assert.throws(
  () => emitter.emit(unit([{ type: 'UnknownStatement', loc: null, _meta: meta }])),
  UnsupportedNodeError,
)

console.log('python-emitter unit tests passed')
