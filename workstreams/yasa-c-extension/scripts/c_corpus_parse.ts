/**
 * Parse every .c/.h file of one or more C projects with parser-C and report
 * parse coverage: crashes, files with tree-sitter syntax errors, functions
 * found by tree-sitter versus FunctionDefinition nodes in the UAST,
 * unhandled node kinds and timing. Optionally dumps each UAST as JSON.
 *
 * Usage (from uast/parser-C so its dependencies resolve):
 *   npx tsx ../../workstreams/yasa-c-extension/scripts/c_corpus_parse.ts \
 *     [--dump OUT_DIR] [--json result.json] PROJECT_DIR...
 */
import * as fs from 'fs';
import * as path from 'path';
import { createRequire } from 'module';

// Resolve parser-C and its dependencies from the current directory (uast/parser-C).
const requireFromParser = createRequire(path.resolve(process.cwd(), 'package.json'));
const TreeSitter = requireFromParser('web-tree-sitter');
const { init, parse } = requireFromParser('./src/parser');

interface ProjectStats {
    project: string;
    files: number;
    lines: number;
    bytes: number;
    crashes: string[];
    filesWithSyntaxErrors: number;
    syntaxErrors: number;
    treeSitterFunctions: number;
    uastFunctions: number;
    unhandled: Record<string, number>;
    buildErrors: number;
    macroExpansions: number;
    parseMs: number;
    slowest: Array<{ file: string; ms: number }>;
}

function listSources(dir: string, out: string[] = []): string[] {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.name === '.git') continue;
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) listSources(full, out);
        else if (/\.[ch]$/.test(entry.name)) out.push(full);
    }
    return out.sort();
}

function walkUast(node: any, visit: (n: any) => void, seen = new Set<any>()): void {
    if (!node || typeof node !== 'object' || seen.has(node)) return;
    seen.add(node);
    if (Array.isArray(node)) return node.forEach((n) => walkUast(n, visit, seen));
    if (typeof node.type === 'string') visit(node);
    for (const [key, value] of Object.entries(node)) {
        if (key !== 'loc' && key !== '_meta' && key !== 'parent') walkUast(value, visit, seen);
    }
}

async function main() {
    const args = process.argv.slice(2);
    const take = (flag: string) => {
        const i = args.indexOf(flag);
        if (i < 0) return undefined;
        const [value] = args.splice(i, 2).slice(1);
        return value;
    };
    const dumpDir = take('--dump');
    const jsonOut = take('--json');
    await init();
    await TreeSitter.Parser.init();
    const cLang = await TreeSitter.Language.load(requireFromParser.resolve('tree-sitter-c/tree-sitter-c.wasm'));
    const tsParser = new TreeSitter.Parser();
    tsParser.setLanguage(cLang);

    const results: ProjectStats[] = [];
    for (const project of args) {
        const stats: ProjectStats = {
            project: path.basename(project), files: 0, lines: 0, bytes: 0, crashes: [], filesWithSyntaxErrors: 0,
            syntaxErrors: 0, treeSitterFunctions: 0, uastFunctions: 0, unhandled: {}, buildErrors: 0,
            macroExpansions: 0, parseMs: 0, slowest: [],
        };
        for (const file of listSources(project)) {
            const code = fs.readFileSync(file, 'utf8');
            stats.files++;
            stats.lines += code.split('\n').length;
            stats.bytes += Buffer.byteLength(code);
            const tree = tsParser.parse(code);
            stats.treeSitterFunctions += tree?.rootNode.descendantsOfType('function_definition').length ?? 0;
            tree?.delete();

            const rel = path.relative(project, file);
            const started = process.hrtime.bigint();
            let unit: any;
            try {
                unit = parse(code, { sourcefile: file });
            } catch (error) {
                stats.crashes.push(`${rel}: ${String((error as Error).message).slice(0, 120)}`);
                continue;
            }
            const ms = Number(process.hrtime.bigint() - started) / 1e6;
            stats.parseMs += ms;
            stats.slowest.push({ file: rel, ms: Math.round(ms) });
            stats.slowest = stats.slowest.sort((a, b) => b.ms - a.ms).slice(0, 5);

            const errors = unit._meta.parseErrors?.length ?? 0;
            stats.syntaxErrors += errors;
            if (errors) stats.filesWithSyntaxErrors++;
            walkUast(unit, (n) => {
                if (n.type === 'FunctionDefinition') stats.uastFunctions++;
                if (n._meta?.unhandled) stats.unhandled[n._meta.unhandled.kind] = (stats.unhandled[n._meta.unhandled.kind] ?? 0) + 1;
                if (n._meta?.buildError) stats.buildErrors++;
                if (n._meta?.macro) stats.macroExpansions++;
            });
            if (dumpDir) {
                const target = path.join(dumpDir, stats.project, `${rel}.json`);
                fs.mkdirSync(path.dirname(target), { recursive: true });
                fs.writeFileSync(target, JSON.stringify(unit));
            }
        }
        stats.parseMs = Math.round(stats.parseMs);
        results.push(stats);
        const fnRatio = stats.treeSitterFunctions ? (100 * stats.uastFunctions / stats.treeSitterFunctions).toFixed(1) : '-';
        console.log(`${stats.project}: ${stats.files} files, ${stats.lines} lines, crashes ${stats.crashes.length}, ` +
            `syntax-error files ${stats.filesWithSyntaxErrors} (${stats.syntaxErrors} regions), ` +
            `functions ${stats.uastFunctions}/${stats.treeSitterFunctions} (${fnRatio}%), build errors ${stats.buildErrors}, ` +
            `macro expansions ${stats.macroExpansions}, parse ${stats.parseMs} ms`);
        console.log(`  unhandled: ${JSON.stringify(stats.unhandled)}`);
        console.log(`  slowest: ${stats.slowest.map((s) => `${s.file} ${s.ms}ms`).join(', ')}`);
        for (const crash of stats.crashes.slice(0, 5)) console.log(`  CRASH ${crash}`);
    }
    if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(results, null, 2));
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
