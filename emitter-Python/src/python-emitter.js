'use strict'

class UnsupportedNodeError extends Error {
  constructor(node, context, reason) {
    super(`Unsupported Python UAST node ${node?.type || typeof node} in ${context}: ${reason}`)
    this.name = 'UnsupportedNodeError'
    this.nodeType = node?.type || typeof node
    this.context = context
    this.location = node?.loc || null
  }
}

class PythonEmitter {
  constructor(options = {}) {
    this.indentText = options.indent || '    '
    this.losses = []
    this.ambiguities = []
    this.nodeCounts = Object.create(null)
    this.listHints = new Set()
  }

  emit(compileUnit) {
    this.losses = []
    this.ambiguities = []
    this.nodeCounts = this.collectNodeCounts(compileUnit)
    this.listHints = this.collectListHints(compileUnit)
    if (!compileUnit || compileUnit.type !== 'CompileUnit') {
      throw new UnsupportedNodeError(compileUnit, 'root', 'expected CompileUnit')
    }
    if (compileUnit.language !== 'python') {
      throw new UnsupportedNodeError(compileUnit, 'root', `expected language=python, got ${compileUnit.language}`)
    }
    const source = `${this.emitStatements(compileUnit.body || [], 0)}\n`
    return {
      source,
      report: {
        status: this.losses.length ? 'lossy' : this.ambiguities.length ? 'ambiguous' : 'canonical',
        deterministic: true,
        language: 'python',
        nodeCounts: { ...this.nodeCounts },
        losses: [...this.losses],
        ambiguities: [...this.ambiguities],
      },
    }
  }

  count(node) {
    // Counting is done once by collectNodeCounts().  Visitor methods retain
    // calls to count() as harmless markers of node-consumption sites.
  }

  collectNodeCounts(root) {
    const counts = Object.create(null)
    const visit = (value) => {
      if (Array.isArray(value)) {
        for (const item of value) visit(item)
        return
      }
      if (!value || typeof value !== 'object') return
      if (typeof value.type === 'string') counts[value.type] = (counts[value.type] || 0) + 1
      for (const [key, item] of Object.entries(value)) {
        if (key !== 'loc' && key !== '_meta') visit(item)
      }
    }
    visit(root)
    return counts
  }

  collectListHints(root) {
    const hints = new Set()
    const visit = (value) => {
      if (Array.isArray(value)) {
        for (const item of value) visit(item)
        return
      }
      if (!value || typeof value !== 'object') return
      if (value.type === 'MemberAccess' && value.object?.type === 'Identifier' &&
          value.property?.type === 'Identifier' && ['append', 'extend', 'insert'].includes(value.property.name)) {
        hints.add(value.object.name)
      }
      for (const [key, item] of Object.entries(value)) {
        if (key !== 'loc' && key !== '_meta') visit(item)
      }
    }
    visit(root)
    return hints
  }

  indent(level) {
    return this.indentText.repeat(level)
  }

  emitStatements(nodes, level) {
    if (!Array.isArray(nodes)) throw new UnsupportedNodeError(nodes, 'statements', 'expected array')
    const lines = []
    for (const node of nodes) {
      const text = this.emitStatement(node, level)
      if (text) lines.push(text)
    }
    return lines.length ? lines.join('\n') : `${this.indent(level)}pass`
  }

  emitStatement(node, level) {
    this.count(node)
    if (!node || typeof node !== 'object') throw new UnsupportedNodeError(node, 'statement', 'expected object')
    const pad = this.indent(level)
    switch (node.type) {
      case 'VariableDeclaration':
        if (node.init?.type === 'ImportExpression') return this.emitImportDeclaration(node, level)
        return `${pad}${this.emitVariableDeclaration(node, 'statement')}`
      case 'Sequence':
        return this.emitStatementSequence(node, level)
      case 'ScopedStatement':
        return this.emitStatements(node.body || [], level)
      case 'AssignmentExpression':
        return `${pad}${this.emitExpression(node.left)} ${this.mapOperator(node.operator)} ${this.emitAssignedValue(node.right, node.left)}`
      case 'ExpressionStatement':
        return `${pad}${this.emitExpression(node.expression)}`
      case 'FunctionDefinition':
        return this.emitFunction(node, level)
      case 'ClassDefinition':
        return this.emitClass(node, level)
      case 'IfStatement':
        return this.emitIf(node, level)
      case 'WhileStatement':
        return `${pad}while ${this.emitExpression(node.test)}:\n${this.emitBlock(node.body, level + 1)}`
      case 'RangeStatement':
        return this.emitRange(node, level)
      case 'ReturnStatement':
        return node.argument && node.argument.type !== 'Noop' ? `${pad}return ${this.emitExpression(node.argument)}` : `${pad}return`
      case 'ThrowStatement':
        return node.argument ? `${pad}raise ${this.emitExpression(node.argument)}` : `${pad}raise`
      case 'TryStatement':
        return this.emitTry(node, level)
      case 'BreakStatement':
        return `${pad}break`
      case 'ContinueStatement':
        return `${pad}continue`
      case 'Noop':
        return `${pad}pass`
      default:
        throw new UnsupportedNodeError(node, 'statement', 'no statement emitter registered')
    }
  }

  emitBlock(node, level) {
    if (!node) return `${this.indent(level)}pass`
    if (node.type === 'ScopedStatement') {
      this.count(node)
      return this.emitStatements(node.body || [], level)
    }
    return this.emitStatement(node, level)
  }

  emitFunction(node, level) {
    const decorators = Array.isArray(node._meta?.decorators) ? node._meta.decorators : []
    const lines = decorators.map((item) => `${this.indent(level)}@${this.emitExpression(item)}`)
    const bodyNodes = node.body?.type === 'ScopedStatement' ? [...(node.body.body || [])] : []
    const syntheticSelf = bodyNodes[0]?.type === 'VariableDeclaration' &&
      this.expressionName(bodyNodes[0].id) === 'self' && bodyNodes[0].init?.type === 'ThisExpression'
    if (syntheticSelf) bodyNodes.shift()
    const params = this.emitParameters(node.parameters || [], syntheticSelf)
    const asyncPrefix = node._meta?.isAsync ? 'async ' : ''
    const name = this.emitExpression(node.id)
    const returnType = node.returnType ? ` -> ${this.emitType(node.returnType)}` : ''
    lines.push(`${this.indent(level)}${asyncPrefix}def ${name}(${params})${returnType}:`)
    lines.push(node.body?.type === 'ScopedStatement'
      ? this.emitStatements(bodyNodes, level + 1)
      : this.emitBlock(node.body, level + 1))
    return lines.join('\n')
  }

  emitClass(node, level) {
    const decorators = Array.isArray(node._meta?.decorators) ? node._meta.decorators : []
    const lines = decorators.map((item) => `${this.indent(level)}@${this.emitExpression(item)}`)
    const supers = (node.supers || []).map((item) => this.emitExpression(item)).join(', ')
    lines.push(`${this.indent(level)}class ${this.emitExpression(node.id)}${supers ? `(${supers})` : ''}:`)
    const body = node.body?.type === 'ScopedStatement' ? node.body.body : node.body
    if (!Array.isArray(body) || body.length === 0) {
      lines.push(`${this.indent(level + 1)}pass`)
    } else {
      lines.push(body.map((item) => item?.type === 'FunctionDefinition'
        ? this.emitFunction(item, level + 1)
        : this.emitStatement(item, level + 1)).join('\n'))
    }
    return lines.join('\n')
  }

  emitIf(node, level) {
    let text = `${this.indent(level)}if ${this.emitExpression(node.test)}:\n${this.emitBlock(node.consequent, level + 1)}`
    if (node.alternative) text += `\n${this.indent(level)}else:\n${this.emitBlock(node.alternative, level + 1)}`
    return text
  }

  emitRange(node, level) {
    const target = node.value || node.key
    if (!target) throw new UnsupportedNodeError(node, 'range', 'missing loop target')
    const targetText = this.emitTarget(target)
    const asyncPrefix = node._meta?.isAsync ? 'async ' : ''
    return `${this.indent(level)}${asyncPrefix}for ${targetText} in ${this.emitExpression(node.right)}:\n${this.emitBlock(node.body, level + 1)}`
  }

  /** Emit a Python assignment target, not a general expression. */
  emitTarget(node) {
    if (!node || typeof node !== 'object') throw new UnsupportedNodeError(node, 'assignment target', 'expected node')
    if (node.type === 'VariableDeclaration') return this.emitTarget(node.id)
    if (node.type === 'TupleExpression') {
      return (node.elements || []).map((item) => this.emitTarget(item)).join(', ')
    }
    if (node.type === 'Sequence') {
      return (node.expressions || []).map((item) => this.emitTarget(item)).join(', ')
    }
    if (node.type === 'DereferenceExpression') return `*${this.emitTarget(node.argument)}`
    return this.emitExpression(node)
  }

  emitTry(node, level) {
    const lines = [`${this.indent(level)}try:`, this.emitBlock(node.body, level + 1)]
    for (const handler of node.handlers || []) {
      if (handler?.type !== 'CatchClause') {
        throw new UnsupportedNodeError(handler, 'try handler', 'expected CatchClause')
      }
      this.count(handler)
      const parameter = (handler.parameter || [])[0]
      let clause = 'except'
      if (parameter?.type === 'VariableDeclaration') {
        const exceptionType = parameter.init ? this.emitExpression(parameter.init) : ''
        // The legacy visitor represents a bare `except:` as a declaration
        // whose id is Literal(value=null, literalType='string'). It is not an
        // exception binding and must not become `except as null`.
        const name = parameter.id?.type === 'Literal' && parameter.id.value === null
          ? ''
          : parameter.id ? this.expressionName(parameter.id) : ''
        if (exceptionType) clause += ` ${exceptionType}`
        if (name && name !== 'None') clause += ` as ${name}`
      }
      lines.push(`${this.indent(level)}${clause}:`)
      lines.push(this.emitBlock(handler.body, level + 1))
    }
    if (node.finalizer?.type === 'ScopedStatement' && (node.finalizer.body || []).length > 0) {
      lines.push(`${this.indent(level)}finally:`)
      lines.push(this.emitBlock(node.finalizer, level + 1))
    }
    if (!(node.handlers || []).length && !(node.finalizer?.body || []).length) {
      throw new UnsupportedNodeError(node, 'try', 'try requires a handler or finalizer')
    }
    return lines.join('\n')
  }

  emitStatementSequence(node, level) {
    const expressions = node.expressions || []
    if (!expressions.length) return `${this.indent(level)}pass`
    const assignments = expressions.every((item) => item?.type === 'AssignmentExpression' && item.operator === '=')
    if (assignments) {
      const serializedRight = JSON.stringify(expressions[0].right)
      if (expressions.every((item) => JSON.stringify(item.right) === serializedRight)) {
        return `${this.indent(level)}${expressions.map((item) => this.emitExpression(item.left)).join(' = ')} = ${this.emitExpression(expressions[0].right)}`
      }
    }
    const deletes = expressions.every((item) => item?.type === 'UnaryExpression' && item.operator === 'delete')
    if (deletes) {
      return `${this.indent(level)}del ${expressions.map((item) => this.emitExpression(item.argument)).join(', ')}`
    }
    this.losses.push({
      kind: 'flattened-sequence',
      message: 'The Python parser erased the original compound-statement boundary; emitted as consecutive statements.',
      location: node.loc || null,
    })
    return expressions.map((item) => this.emitStatement(item, level)).join('\n')
  }

  emitImportDeclaration(node, level) {
    this.count(node.init)
    const imp = node.init
    const local = this.expressionName(node.id)
    if (imp.from) {
      const from = this.literalValue(imp.from)
      const imported = this.expressionName(imp.imported)
      return `${this.indent(level)}from ${from} import ${imported}${local && local !== imported ? ` as ${local}` : ''}`
    }
    const imported = this.expressionName(imp.imported)
    return `${this.indent(level)}import ${imported}${local && local !== imported ? ` as ${local}` : ''}`
  }

  emitParameter(node) {
    if (!node || node.type !== 'VariableDeclaration') throw new UnsupportedNodeError(node, 'parameter', 'expected VariableDeclaration')
    this.count(node)
    const kind = node._meta?.parameterKind || 'positional_or_keyword'
    const prefix = kind === 'vararg' ? '*' : ['kwarg', 'varkw'].includes(kind) ? '**' : ''
    let text = `${prefix}${this.emitExpression(node.id)}`
    if (node.varType && node.varType.type !== 'DynamicType') text += `: ${this.emitType(node.varType)}`
    if (node.init) text += ` = ${this.emitExpression(node.init)}`
    return text
  }

  emitParameters(nodes, includeSelf) {
    const output = includeSelf ? ['self'] : []
    let insertedKeywordSeparator = false
    let positionalOnlyCount = 0
    for (const node of nodes) {
      const kind = node?._meta?.parameterKind || 'positional_or_keyword'
      if (kind === 'keyword_only' && !insertedKeywordSeparator && !nodes.some((item) => item?._meta?.parameterKind === 'vararg')) {
        output.push('*')
        insertedKeywordSeparator = true
      }
      output.push(this.emitParameter(node))
      if (kind === 'positional_only') positionalOnlyCount = output.length
      if (kind === 'vararg') insertedKeywordSeparator = true
    }
    if (positionalOnlyCount) output.splice(positionalOnlyCount, 0, '/')
    return output.join(', ')
  }

  emitVariableDeclaration(node, context) {
    this.count(node)
    const id = this.emitExpression(node.id)
    if (context === 'argument') return `${id}=${this.emitExpression(node.init)}`
    const annotation = node.varType && node.varType.type !== 'DynamicType' ? `: ${this.emitType(node.varType)}` : ''
    return node.init ? `${id}${annotation} = ${this.emitAssignedValue(node.init, node.id)}` : `${id}${annotation}`
  }

  emitAssignedValue(value, target) {
    if (value?.type === 'ObjectExpression' && (value.properties || []).length === 0) {
      const name = target?.type === 'Identifier' ? target.name : null
      return this.emitObject(value, name && this.listHints.has(name) ? 'list' : 'dict')
    }
    return this.emitExpression(value)
  }

  emitExpression(node) {
    this.count(node)
    if (node === null || node === undefined) return 'None'
    if (typeof node === 'string') return node
    if (typeof node !== 'object') return String(node)
    switch (node.type) {
      case 'Identifier':
        return node.name
      case 'Literal':
        return this.emitLiteral(node)
      case 'CallExpression':
        return `${this.emitExpression(node.callee)}(${(node.arguments || []).map((arg) => this.emitCallArgument(arg)).join(', ')})`
      case 'MemberAccess':
        return this.emitMemberAccess(node)
      case 'AssignmentExpression':
        return `(${this.emitExpression(node.left)} ${this.mapOperator(node.operator)} ${this.emitAssignedValue(node.right, node.left)})`
      case 'BinaryExpression':
        return `(${this.emitExpression(node.left)} ${this.mapOperator(node.operator)} ${this.emitExpression(node.right)})`
      case 'UnaryExpression': {
        const op = this.mapOperator(node.operator)
        return node.isSuffix ? `(${this.emitExpression(node.argument)}${op})` : `(${op}${op === 'not' ? ' ' : ''}${this.emitExpression(node.argument)})`
      }
      case 'ObjectExpression':
        return this.emitObject(node)
      case 'FunctionDefinition':
        return this.emitLambda(node)
      case 'TupleExpression': {
        const values = (node.elements || []).map((item) => this.emitExpression(item))
        return `(${values.join(', ')}${values.length === 1 ? ',' : ''})`
      }
      case 'SliceExpression':
        return this.emitSlice(node)
      case 'ConditionalExpression':
        return `(${this.emitExpression(node.consequent)} if ${this.emitExpression(node.test)} else ${this.emitExpression(node.alternative)})`
      case 'ThisExpression':
        return 'self'
      case 'SuperExpression':
        return 'super()'
      case 'Sequence':
        return `(${(node.expressions || []).map((item) => this.emitExpression(item)).join(', ')})`
      case 'VariableDeclaration':
        if (!node.init) throw new UnsupportedNodeError(node, 'named expression', 'missing value')
        return `(${this.emitExpression(node.id)} := ${this.emitExpression(node.init)})`
      case 'NewExpression':
        return `${this.emitExpression(node.callee)}(${(node.arguments || []).map((item) => this.emitExpression(item)).join(', ')})`
      case 'DereferenceExpression':
        return `*${this.emitExpression(node.argument)}`
      case 'ReferenceExpression':
        this.losses.push({ kind: 'reference-expression', message: 'Python has no explicit reference operator; emitted the referenced value.', location: node.loc || null })
        return this.emitExpression(node.argument)
      case 'SpreadElement':
        return `**${this.emitExpression(node.argument)}`
      case 'YieldExpression': {
        const argument = Array.isArray(node.argument) ? node.argument[0] : node.argument
        return argument ? `yield ${this.emitExpression(argument)}` : 'yield'
      }
      case 'CastExpression':
        this.losses.push({ kind: 'cast-expression', message: 'Python type casts are not represented uniformly; emitted the underlying expression.', location: node.loc || null })
        return this.emitExpression(node.expression)
      case 'Noop':
        return 'None'
      default:
        throw new UnsupportedNodeError(node, 'expression', 'no expression emitter registered')
    }
  }

  emitCallArgument(node) {
    if (node?.type === 'VariableDeclaration') return this.emitVariableDeclaration(node, 'argument')
    if (node?.type === 'SpreadElement') return `**${this.emitExpression(node.argument)}`
    if (node?.type === 'DereferenceExpression') return `*${this.emitExpression(node.argument)}`
    return this.emitExpression(node)
  }

  emitLambda(node) {
    if (node.id) throw new UnsupportedNodeError(node, 'lambda', 'named FunctionDefinition is not an expression')
    const body = node.body?.type === 'ScopedStatement' ? node.body.body || [] : []
    if (body.length !== 1 || body[0]?.type !== 'ReturnStatement') {
      throw new UnsupportedNodeError(node, 'lambda', 'lambda body must contain exactly one ReturnStatement')
    }
    return `(lambda ${this.emitParameters(node.parameters || [], false)}: ${this.emitExpression(body[0].argument)})`
  }

  emitMemberAccess(node) {
    const object = this.emitExpression(node.object)
    if (node.property?.type === 'SliceExpression') return `${object}[${this.emitSlice(node.property)}]`
    // Python multi-dimensional subscription is represented by the legacy
    // visitor as Sequence([SliceExpression, ...]), not as a tuple expression.
    if (node.property?.type === 'Sequence') {
      const indices = (node.property.expressions || []).map((item) =>
        item?.type === 'SliceExpression' ? this.emitSlice(item) : this.emitExpression(item)
      )
      return `${object}[${indices.join(', ')}]`
    }
    if (node.computed || node.property?.type !== 'Identifier') return `${object}[${this.emitExpression(node.property)}]`
    return `${object}.${this.emitExpression(node.property)}`
  }

  emitSlice(node) {
    this.count(node)
    const start = node.start ? this.emitExpression(node.start) : ''
    const end = node.end ? this.emitExpression(node.end) : ''
    const step = node.step ? `:${this.emitExpression(node.step)}` : ''
    return `${start}:${end}${step}`
  }

  emitObject(node, emptyHint = null) {
    const properties = node.properties || []
    if (properties.length === 0) {
      this.ambiguities.push({
        kind: 'empty-container-ambiguity',
        message: `An empty Python list and dict share the same UAST; emitted ${emptyHint === 'list' ? 'list from usage hint' : 'dict by default'}.`,
        location: node.loc || null,
      })
      return emptyHint === 'list' ? '[]' : '{}'
    }
    const isList = properties.length > 0 && properties.every((property, index) =>
      property?.type === 'ObjectProperty' && property.key?.type === 'Literal' && property.key.value === index)
    if (isList) {
      this.ambiguities.push({
        kind: 'indexed-container-ambiguity',
        message: 'Python list, set, and sequential-integer-key dict share this UAST shape; emitted list.',
        location: node.loc || null,
      })
      return `[${properties.map((property) => this.emitExpression(property.value)).join(', ')}]`
    }
    return `{${properties.map((property) => {
      if (property?.type === 'SpreadElement') return `**${this.emitExpression(property.argument)}`
      if (property?.type !== 'ObjectProperty') throw new UnsupportedNodeError(property, 'object', 'expected ObjectProperty or SpreadElement')
      return `${this.emitExpression(property.key)}: ${this.emitExpression(property.value)}`
    }).join(', ')}}`
  }

  emitLiteral(node) {
    // The legacy Python visitor stores None as literalType=null (the JSON null
    // value), while other UAST producers may use the string "null".
    if (node.literalType === null || node.literalType === 'null' || node.value === null) return 'None'
    if (node.literalType === 'boolean') return node.value === true || node.value === 'True' ? 'True' : 'False'
    if (node.literalType === 'string') return JSON.stringify(String(node.value))
    if (node.literalType === 'bytes') return `b${JSON.stringify(String(node.value))}`
    if (node.literalType === 'float' && Number.isInteger(node.value)) return `${node.value}.0`
    if (node.literalType === 'number' && typeof node.value === 'string' && /^[0-9]+$/.test(node.value)) return node.value
    if (typeof node.value === 'number') return String(node.value)
    throw new UnsupportedNodeError(node, 'literal', `unsupported literal type ${node.literalType}`)
  }

  emitType(node) {
    this.count(node)
    switch (node?.type) {
      case 'Identifier': return node.name
      // Python annotations are expressions too: e.g. torch.dtype, "Tensor",
      // and PEP 604 unions such as Tensor | None.
      case 'MemberAccess': return this.emitExpression(node)
      case 'Literal': return this.emitLiteral(node)
      case 'BinaryExpression': return this.emitExpression(node)
      case 'DynamicType': return node.id?.type === 'Identifier' ? node.id.name : typeof node.id === 'string' ? node.id : 'object'
      case 'PrimitiveType': {
        const id = node.id?.type === 'Identifier' ? node.id.name : null
        if (id && id !== 'PrimitiveType') return id
        if (node.kind === 'number') {
          this.ambiguities.push({
            kind: 'numeric-type-ambiguity',
            message: 'PrimitiveType(kind=number) does not distinguish Python int from float; emitted float.',
            location: node.loc || null,
          })
        }
        return ({ number: 'float', string: 'str', boolean: 'bool', null: 'None' })[node.kind] || 'object'
      }
      case 'ArrayType': return `list[${node.element ? this.emitType(node.element) : 'object'}]`
      case 'MapType': return `dict[${node.keyType ? this.emitType(node.keyType) : 'object'}, ${node.valueType ? this.emitType(node.valueType) : 'object'}]`
      case 'ScopedType': return this.emitExpression(node.id)
      case 'TupleType': return `tuple[${(node.elements || []).map((item) => this.emitType(item)).join(', ')}]`
      case 'VoidType': return 'None'
      default: throw new UnsupportedNodeError(node, 'type', 'no type emitter registered')
    }
  }

  mapOperator(operator) {
    return ({ '&&': 'and', '||': 'or', '!': 'not', instanceof: 'is', '!instanceof': 'is not', '!in': 'not in' })[operator] || operator
  }

  expressionName(node) {
    if (node?.type === 'Identifier') return node.name
    if (node?.type === 'Literal') return String(node.value)
    return node ? this.emitExpression(node) : ''
  }

  literalValue(node) {
    if (node?.type === 'Literal') return String(node.value)
    return this.emitExpression(node)
  }
}

module.exports = { PythonEmitter, UnsupportedNodeError }
