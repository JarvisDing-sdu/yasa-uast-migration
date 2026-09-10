import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import { Parser } from '../src';
import { fileURLToPath } from 'node:url';

function files(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
        entry.isDirectory() &&
        !['.git', '.venv', 'node_modules', '__pycache__'].includes(entry.name)
            ? files(join(dir, entry.name))
            : entry.isFile() && entry.name.endsWith('.py')
              ? [join(dir, entry.name)]
              : []
    );
}
function differences(a: any, b: any, path = ''): string[] {
    if (isDeepStrictEqual(a, b)) return [];
    if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object')
        return [`${path}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`];
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].flatMap((key) =>
        differences(a[key], b[key], path + '.' + key)
    );
}
async function main() {
    if (!process.argv[2] || !process.env.PYTHON_UAST_ORACLE)
        throw new Error('Set PYTHON_UAST_ORACLE and pass a corpus directory.');
    const paths = files(resolve(process.argv[2]));
    const sources = paths.map((file) => readFileSync(file, 'utf8'));
    const oracle = spawnSync(
        process.env.PYTHON_UAST_ORACLE,
        [fileURLToPath(new URL('./legacy.py', import.meta.url)), '--batch'],
        { input: JSON.stringify(sources), encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 }
    );
    if (oracle.status !== 0) throw new Error(oracle.stderr);
    const old = JSON.parse(oracle.stdout);
    const parser = new Parser({ sourcefile: 'fixture.py' });
    await parser.init();
    let equal = 0;
    const failures: any[] = [];
    paths.forEach((file, i) => {
        if (old[i].error) {
            failures.push({ file, legacyError: old[i].error });
            return;
        }
        try {
            const diff = differences((parser.parse(sources[i]) as any).body, old[i].body);
            if (diff.length)
                failures.push({
                    file,
                    count: diff.length,
                    locationOnly: diff.every((d) => d.includes('.loc')),
                    differences: diff.slice(0, 8),
                });
            else equal++;
        } catch (error) {
            failures.push({ file, error: String(error) });
        }
    });
    console.log(
        JSON.stringify(
            {
                total: paths.length,
                equal,
                different: failures.length,
                locationOnly: failures.filter((f) => f.locationOnly).length,
                failures: failures
                    .sort((a, b) => Number(a.locationOnly) - Number(b.locationOnly))
                    .slice(0, Number(process.env.DIFF_LIMIT || 12)),
            },
            null,
            2
        )
    );
    if (failures.length) process.exitCode = 1;
}
main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
