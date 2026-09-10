import { Parser as TreeParser, Language, type Node as SyntaxNode } from 'web-tree-sitter';
import type * as UAST from '@ant-yasa/uast-spec';
import { dirname, join } from 'node:path';
import { Visitor } from './visitor';

export interface ParseOptions {
    sourcefile?: string;
}

let parser: TreeParser | undefined;
let initializing: Promise<void> | undefined;

export function init(): Promise<void> {
    if (parser) return Promise.resolve();
    if (!initializing) {
        initializing = (async () => {
            await TreeParser.init();
            // Resolve the package, then join the asset filename: pkg must not
            // classify a literal require.resolve('*.wasm') as JavaScript.
            const grammarRoot = dirname(require.resolve('tree-sitter-python/package.json'));
            const language = await Language.load(join(grammarRoot, 'tree-sitter-python.wasm'));
            const instance = new TreeParser();
            instance.setLanguage(language);
            parser = instance;
        })().catch((error) => {
            initializing = undefined;
            throw error;
        });
    }
    return initializing;
}

function syntaxError(node: SyntaxNode): SyntaxNode {
    for (const child of node.children) {
        if (child.hasError || child.isMissing) return syntaxError(child);
    }
    return node;
}

export function parse(content: string, opts: ParseOptions = {}): UAST.Node {
    if (!parser) throw new Error('Parser not initialized. Call init() first.');
    // Match the old Engine's UTF-8 BOM retry, including normalized locations.
    content = content.replace(/^\uFEFF/, '');
    let tree = parser.parse(content);
    if (!tree) throw new Error('tree-sitter failed to produce a Python syntax tree');
    try {
        if (tree.rootNode.hasError) {
            // Retry legacy soft keywords without changing offsets or string/comment
            // contents. Visitor reads identifier spellings from the original source.
            const protectedRanges: [number, number][] = [];
            const protect = (node: SyntaxNode) => {
                if (['string', 'comment'].includes(node.type))
                    protectedRanges.push([node.startIndex, node.endIndex]);
                else node.namedChildren.forEach(protect);
            };
            protect(tree.rootNode);
            const compatible = content.replace(/\b(async|await)\b/g, (word, _group, offset) => {
                if (protectedRanges.some(([start, end]) => offset >= start && offset < end))
                    return word;
                if (
                    word === 'async' &&
                    /^\s+(def|for|with)\b/.test(content.slice(offset + word.length))
                )
                    return word;
                return word === 'async' ? 'asynx' : 'awaix';
            });
            if (compatible !== content) {
                const retry = parser.parse(compatible);
                if (retry) {
                    tree.delete();
                    tree = retry;
                }
            }
        }
        if (tree.rootNode.hasError) {
            const node = syntaxError(tree.rootNode);
            throw new SyntaxError(
                `${opts.sourcefile || '<python>'}:${node.startPosition.row + 1}:${node.startPosition.column + 1}: invalid Python syntax (${node.type})`
            );
        }
        return new Visitor(content, opts.sourcefile).compile(tree.rootNode);
    } finally {
        tree.delete();
    }
}
