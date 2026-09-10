/** Read-only corpus check: npm run test:corpus -- /path/to/python/project */
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import { Parser } from '../src';

function* files(dir: string): Generator<string> {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (
            entry.isDirectory() &&
            !['.git', '.venv', 'node_modules', '__pycache__'].includes(entry.name)
        )
            yield* files(join(dir, entry.name));
        if (entry.isFile() && entry.name.endsWith('.py')) yield join(dir, entry.name);
    }
}

async function main() {
    if (!process.argv[2]) throw new Error('Usage: npm run test:corpus -- /path/to/python/project');
    const parser = new Parser();
    const start = performance.now();
    await parser.init();
    const initialized = performance.now();
    const failures: { file: string; error: string }[] = [];
    let parsed = 0;
    for (const file of files(resolve(process.argv[2]))) {
        try {
            parser.parse(readFileSync(file, 'utf8'), { sourcefile: file });
            parsed++;
        } catch (error) {
            failures.push({ file, error: String(error) });
        }
    }
    console.log(
        JSON.stringify(
            {
                parsed,
                failed: failures.length,
                initializationMs: initialized - start,
                parseAndReadMs: performance.now() - initialized,
                rssMiB: process.memoryUsage().rss / 1024 / 1024,
                failures,
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
