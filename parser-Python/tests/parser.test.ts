import assert from 'node:assert/strict';
import { test, before } from 'node:test';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Parser } from '../src';
import * as UAST from '@ant-yasa/uast-spec';

const parser = new Parser({ sourcefile: 'fixture.py' });
before(async () => {
    await Promise.all([parser.init(), parser.init(), new Parser().init()]);
});
const body = (code: string): any[] => (parser.parse(code) as any).body;

test('normalizes UTF-8 BOM and explicitly rejects unsupported string semantics', () => {
    assert.deepEqual(parser.parse('\uFEFFx = 1'), parser.parse('x = 1'));
    for (const source of [String.raw`x = "\N{SNOWMAN}"`, 'x = t"hello"'])
        assert.throws(() => parser.parse(source), SyntaxError);
    assert.equal(body(String.raw`x = r"\N{SNOWMAN}"`)[0].right.value, String.raw`\N{SNOWMAN}`);
    assert.equal(body(String.raw`x = "\\N{SNOWMAN}"`)[0].right.value, String.raw`\N{SNOWMAN}`);
    assert.equal(body('obj.async = 1')[0].left.property.name, 'async');
    assert.equal(body('f(async=1)')[0].expression.arguments[0].id.name, 'async');
});

test('debug f-strings preserve labels, whitespace, expressions and text merging', () => {
    const result = body('x = f"hi { value = !r:>3} after {other=}"')[0].right;
    assert.equal(result.left.left.left.value, 'hi  value = ');
    assert.equal(result.left.left.right.name, 'value');
    assert.equal(result.left.right.value, ' after other=');
    assert.equal(result.right.name, 'other');
    const only = body('x = f"{名字=}"')[0].right;
    assert.equal(only.left.value, '名字=');
    assert.equal(only.left.loc.end.column - only.left.loc.start.column, 7);
});

test('assignments, imports, calls, self and parameter kinds retain Python UAST conventions', () => {
    const result = body(
        'from os import system as run\nclass A:\n def __init__(self, x:int=1, /, *args, flag=True, **kwargs):\n  self.x = x\n  run(flag=flag, **kwargs)\n'
    );
    assert.equal(result[0].init.from.value, 'os');
    assert.equal(result[0].id.name, 'run');
    const ctor = result[1].body[0];
    assert.equal(ctor._meta.isConstructor, true);
    assert.deepEqual(
        ctor.parameters.map((p: any) => p._meta.parameterKind),
        ['positional_only', 'vararg', 'keyword_only', 'varkw']
    );
    assert.equal(ctor.parameters[0].init.value, 1);
    assert.equal(ctor.body.body[0].init.type, 'ThisExpression');
    assert.equal(ctor.body.body[2].expression.arguments[1].type, 'SpreadElement');
});

test('official Python examples parse', () => {
    for (const fixture of ['test_type_annotations.py', 'example.py', 'import.py']) {
        assert.ok(
            body(readFileSync(new URL('../test/' + fixture, import.meta.url), 'utf8')).length
        );
    }
});

test('legacy async/await identifier compatibility and real async statements', () => {
    for (const source of [
        'from trainer import async\nx = async(1)',
        'await = 42\nprint(await)',
        'def async(x):\n return x + 1',
    ])
        assert.ok(body(source).length);
    const fn = body(
        'async def f():\n async for x in xs:\n  await sink(x)\n async with ctx() as c:\n  pass'
    )[0];
    assert.equal(fn._meta.isAsync, true);
    assert.equal(fn.body.body[0]._meta.isAsync, true);
    assert.equal(fn.body.body[1]._meta.isAsync, true);
});

test('rejects syntax errors, recovers for the next parse, and handles empty files', () => {
    for (const source of ['def foo(\n pass', 'x =', 'def f():\n'])
        assert.throws(() => parser.parse(source), SyntaxError);
    assert.equal(body('x = 1')[0].right.value, 1);
    assert.deepEqual(body('# comment\n'), []);
});

test('UTF-8 locations and per-call source filenames', () => {
    const ast: any = parser.parse('名字 = "😀"\nx = 名字\n', { sourcefile: 'unicode.py' });
    assert.equal(ast.body[0].left.loc.end.column, 7);
    assert.equal(ast.body[0].right.loc.start.column, 10);
    assert.equal(ast.body[0].loc.sourcefile, 'unicode.py');
    assert.equal(body('x=1')[0].loc.sourcefile, 'fixture.py');
});

test('nested comprehensions retain each loop and condition and reset temporary IDs', () => {
    const source = 'result = [sink(x,y) for x in xs if x for y in ys if y]';
    assert.deepEqual(body(source), body(source));
    const sequence = body(source)[0].right;
    assert.equal(sequence.expressions[0].id.name, '__tmp1__');
    assert.equal(sequence.expressions[1].body.body[0].consequent.body[0].type, 'RangeStatement');
});

test('match patterns, guards, f-strings, slices and dataclass constructor', () => {
    assert.equal(
        body(
            'match x:\n case [a, *rest] if a: sink(a)\n case {"x": x, **rest}: pass\n case Point(x, y=z): pass'
        )[0].cases.length,
        3
    );
    assert.equal(body('x = f"hi {name}!"')[0].right.type, 'BinaryExpression');
    assert.equal(body('x = a[1:9:2]')[0].right.property.step.value, 2);
    const cls = body('@dataclass\nclass A:\n x: int\n y: str = "ok"')[0];
    assert.equal(cls.body.at(-1)._meta.isConstructor, true);
    assert.equal(cls.body.at(-1).parameters.length, 2);
});

test('result supports the shared UAST traversal API', () => {
    const nodes: string[] = [];
    UAST.traverseFast(parser.parse('def f(x):\n return sink(x)'), (node) => {
        nodes.push(node.type);
    });
    assert.ok(nodes.includes('FunctionDefinition'));
    assert.ok(nodes.includes('CallExpression'));
});

test('real-project regressions: comments, continuations, with items, bytes and wildcard patterns', () => {
    const source = 'def f():\n return x # trailing comment';
    assert.equal(body(source)[0].loc.end.column, 10);
    assert.deepEqual(body('x = b"abc"')[0].right.value, [97, 98, 99]);
    assert.deepEqual(body('x = b"a" b"b"')[0].right.value, [97, 98]);
    assert.ok(body('with (ctx() as x,\n other() as y):\n pass').length);
    assert.ok(body('x = 1 + \\\n 2').length);
    assert.ok(body('match x:\n case Point(_): pass').length);
    assert.equal(body('x = f""')[0].right, null);
    const call = body('f(key=1, *args)')[0].expression;
    assert.equal(call.arguments[0].type, 'DereferenceExpression');
});

const oracle = process.env.PYTHON_UAST_ORACLE;
test('debug f-string semantics match the legacy visitor', { skip: !oracle }, () => {
    // CPython <=3.13 gives text segments different source ranges than 3.14.
    const withoutLocations = (value: any): any => {
        if (Array.isArray(value)) return value.map(withoutLocations);
        if (value && typeof value === 'object')
            return Object.fromEntries(
                Object.entries(value)
                    .filter(([key]) => key !== 'loc')
                    .map(([key, child]) => [key, withoutLocations(child)])
            );
        return value;
    };
    for (const source of [
        'x = f"hi { x = } after {y=}"',
        'x = f"{x=} { x = !r:>3}"',
        'x = f"{名字=}"',
    ]) {
        const old = spawnSync(oracle!, [fileURLToPath(new URL('./legacy.py', import.meta.url))], {
            input: source,
            encoding: 'utf8',
            maxBuffer: 32 * 1024 * 1024,
        });
        assert.equal(old.status, 0, old.stderr);
        assert.deepEqual(withoutLocations(body(source)), withoutLocations(JSON.parse(old.stdout)));
    }
});
for (const fixture of ['test_type_annotations.py', 'example.py', 'import.py']) {
    test(`legacy body equality: ${fixture}`, { skip: !oracle }, () => {
        const source = readFileSync(new URL('../test/' + fixture, import.meta.url), 'utf8');
        const old = spawnSync(oracle!, [fileURLToPath(new URL('./legacy.py', import.meta.url))], {
            input: source,
            encoding: 'utf8',
            maxBuffer: 32 * 1024 * 1024,
        });
        assert.equal(old.status, 0, old.stderr);
        assert.deepEqual(body(source), JSON.parse(old.stdout));
    });
}

test(
    'complete CompileUnit envelope matches the legacy type-annotation baseline',
    { skip: !oracle },
    () => {
        const source = readFileSync(
            new URL('../test/test_type_annotations.py', import.meta.url),
            'utf8'
        );
        const old = spawnSync(
            oracle!,
            [fileURLToPath(new URL('./legacy.py', import.meta.url)), '--unit'],
            { input: source, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }
        );
        assert.equal(old.status, 0, old.stderr);
        assert.deepEqual(parser.parse(source), JSON.parse(old.stdout));
    }
);
