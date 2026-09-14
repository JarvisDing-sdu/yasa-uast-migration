import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { before, test } from 'node:test';
import { Parser } from '../src';

type ComparisonMode = 'exact' | 'without-loc' | 'legacy-gap';

interface SemanticCase {
    name: string;
    source: string;
    requiredTypes: string[];
    mode?: ComparisonMode;
}

/**
 * A compact, syntax-focused regression corpus. Every case is intentionally
 * self-contained so that a failure identifies a Python language construct.
 */
const cases: SemanticCase[] = [
    {
        name: 'literals and containers',
        source: 'a = None\nb = True\nc = b"xy"\nd = [1, 2]\ne = {"x": 1}\nf = (1,)\ng = {1, 2}\n',
        requiredTypes: ['Literal', 'ObjectExpression', 'TupleExpression'],
    },
    {
        name: 'assignment forms',
        source: 'a = b = 1\nx, y = (2, 3)\nx += y\n',
        requiredTypes: ['Sequence', 'AssignmentExpression', 'BinaryExpression'],
    },
    {
        name: 'imports and aliases',
        source: 'import os.path as osp\nfrom .pkg import thing as local_thing\n',
        requiredTypes: ['ImportExpression', 'VariableDeclaration'],
    },
    {
        name: 'function parameters annotations and decorators',
        source: '@decorator\ndef f(a: int, /, b: str = "x", *args, flag: bool = True, **kwargs) -> list[int]:\n    return [a]\n',
        requiredTypes: ['FunctionDefinition', 'VariableDeclaration', 'ArrayType', 'ReturnStatement'],
    },
    {
        name: 'lambda conditional and named expression',
        source: 'fn = lambda x: x if (y := x + 1) > 0 else -x\n',
        requiredTypes: ['FunctionDefinition', 'ConditionalExpression', 'VariableDeclaration'],
    },
    {
        name: 'class constructor inheritance and self',
        source: 'class Child(Base):\n    def __init__(self, value):\n        self.value = value\n    def get(self):\n        return self.value\n',
        requiredTypes: ['ClassDefinition', 'FunctionDefinition', 'ThisExpression', 'MemberAccess'],
    },
    {
        name: 'if elif else',
        source: 'if x > 0:\n    y = 1\nelif x == 0:\n    y = 0\nelse:\n    y = -1\n',
        requiredTypes: ['IfStatement', 'BinaryExpression', 'ScopedStatement'],
    },
    {
        name: 'for while break continue',
        source: 'for key, value in items:\n    if key < 0:\n        continue\n    if value == 0:\n        break\nwhile ready:\n    ready = False\n',
        requiredTypes: ['RangeStatement', 'WhileStatement', 'BreakStatement', 'ContinueStatement'],
    },
    {
        name: 'try except finally raise',
        source: 'try:\n    value = work()\nexcept ValueError as error:\n    raise RuntimeError(error)\nfinally:\n    cleanup()\n',
        requiredTypes: ['TryStatement', 'CatchClause', 'ThrowStatement'],
    },
    {
        name: 'with statement',
        source: 'with open(path) as handle, lock:\n    data = handle.read()\n',
        requiredTypes: ['Sequence', 'VariableDeclaration', 'CallExpression'],
    },
    {
        name: 'calls keyword and spread arguments',
        source: 'result = target(a, key=1, *extra, **options)\n',
        requiredTypes: ['CallExpression', 'VariableDeclaration', 'DereferenceExpression', 'SpreadElement'],
    },
    {
        name: 'member access indexing and slicing',
        source: 'value = obj.field[1:9:2]\n',
        requiredTypes: ['MemberAccess', 'SliceExpression'],
    },
    {
        name: 'operators comparisons and boolean chains',
        source: 'ok = (a + b * c >= d) and x not in values and y is not None\n',
        requiredTypes: ['BinaryExpression'],
        // The legacy visitor leaves synthetic intermediate boolean-chain nodes
        // without locations; the Tree-sitter visitor assigns their full spans.
        mode: 'without-loc',
    },
    {
        name: 'list dictionary and generator comprehensions',
        source: 'items = [f(x) for x in xs if x]\nmapping = {x: f(x) for x in xs if x}\nstream = (f(x) for x in xs if x)\n',
        requiredTypes: ['Sequence', 'RangeStatement'],
    },
    {
        name: 'yield and yield from',
        source: 'def values(xs):\n    yield 1\n    yield from xs\n',
        requiredTypes: ['YieldExpression', 'FunctionDefinition'],
    },
    {
        name: 'async function async for and async with',
        source: 'async def consume(stream, ctx):\n    async for value in stream:\n        await sink(value)\n    async with ctx() as resource:\n        return resource\n',
        requiredTypes: ['FunctionDefinition', 'RangeStatement', 'Sequence'],
    },
    {
        name: 'match patterns and guard',
        source: 'match value:\n    case [head, *tail] if head > 0:\n        sink(head)\n    case {"name": name, **rest}:\n        sink(name)\n    case _:\n        pass\n',
        requiredTypes: ['SwitchStatement', 'CaseClause', 'IfStatement'],
        // The old visitor discarded match guards. The new visitor preserves a
        // guard as an IfStatement inside the corresponding CaseClause body.
        mode: 'legacy-gap',
    },
    {
        name: 'dataclass synthesis',
        source: '@dataclass\nclass Point:\n    x: int\n    y: int = 0\n',
        requiredTypes: ['ClassDefinition', 'FunctionDefinition', 'VariableDeclaration'],
    },
    {
        name: 'f-string semantic structure',
        source: 'message = f"user={name!r}, score={score:>3}"\n',
        requiredTypes: ['BinaryExpression', 'Identifier'],
        // The two parser implementations intentionally differ in the source
        // range assigned to some f-string text fragments.
        mode: 'without-loc',
    },
];

const parser = new Parser({ sourcefile: 'fixture.py' });
const oracle = process.env.PYTHON_UAST_ORACLE;

before(async () => {
    await parser.init();
});

function collectTypes(value: any, output = new Set<string>()): Set<string> {
    if (Array.isArray(value)) value.forEach((item) => collectTypes(item, output));
    else if (value && typeof value === 'object') {
        if (typeof value.type === 'string') output.add(value.type);
        Object.entries(value).forEach(([key, item]) => {
            if (key !== 'loc' && key !== '_meta') collectTypes(item, output);
        });
    }
    return output;
}

function withoutLoc(value: any): any {
    if (Array.isArray(value)) return value.map(withoutLoc);
    if (value && typeof value === 'object') {
        return Object.fromEntries(
            Object.entries(value)
                .filter(([key]) => key !== 'loc')
                .map(([key, item]) => [key, withoutLoc(item)])
        );
    }
    return value;
}

function legacyBody(source: string): any {
    const legacy = spawnSync(
        oracle!,
        [fileURLToPath(new URL('./legacy.py', import.meta.url))],
        { input: source, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }
    );
    assert.equal(legacy.status, 0, legacy.stderr);
    return JSON.parse(legacy.stdout);
}

test('semantic matrix: new parser covers common Python UAST units', () => {
    assert.equal(cases.length, 19);
    for (const item of cases) {
        const ast: any = parser.parse(item.source);
        assert.equal(ast.type, 'CompileUnit', item.name);
        const actualTypes = collectTypes(ast.body);
        for (const requiredType of item.requiredTypes) {
            assert.ok(actualTypes.has(requiredType), `${item.name}: missing ${requiredType}`);
        }
    }
});

test(
    'semantic matrix: compatibility cases match the legacy Python visitor',
    { skip: !oracle },
    () => {
        for (const item of cases) {
            const actual = (parser.parse(item.source) as any).body;
            const expected = legacyBody(item.source);
            if (item.mode === 'legacy-gap') {
                assert.notDeepEqual(withoutLoc(actual), withoutLoc(expected), item.name);
                continue;
            }
            const normalizedActual = item.mode === 'without-loc' ? withoutLoc(actual) : actual;
            const normalizedExpected = item.mode === 'without-loc' ? withoutLoc(expected) : expected;
            assert.deepEqual(normalizedActual, normalizedExpected, item.name);
        }
    }
);
