#!/usr/bin/env python3
"""Compare internal C function-pair call edges against an explicit reference.

Reference input is either a hand-labelled gold.json or one Clang AST JSON.
No third-party Python packages are required. External/unknown targets are out
of scope; unresolved internal targets still appear as missing gold edges.
"""
import argparse
import collections
import json
from pathlib import Path
import sqlite3


def walk(node):
    yield node
    for child in node.get('inner', []):
        yield from walk(child)


def reference(args):
    if args.gold:
        data = json.loads(Path(args.gold).read_text())
        definitions = {tuple(x) for x in data['definitions']}
        truth = {(tuple(e['caller']), tuple(e['callee'])) for e in data['edges']}
        categories = {(tuple(e['caller']), tuple(e['callee'])): e['category'] for e in data['edges']}
        return definitions, truth, categories
    ast = json.loads(Path(args.clang_ast).read_text())
    source = Path(args.source_file).name
    funcs = {
        n['name']: n for n in walk(ast)
        if n.get('kind') == 'FunctionDecl'
        and not n.get('loc', {}).get('includedFrom')
        and any(c.get('kind') == 'CompoundStmt' for c in n.get('inner', []))
    }
    definitions = {(source, name) for name in funcs}
    truth = set()
    for caller, func in funcs.items():
        for call in walk(func):
            if call.get('kind') != 'CallExpr' or not call.get('inner'):
                continue
            for ref in walk(call['inner'][0]):
                decl = ref.get('referencedDecl', {})
                if (ref.get('kind') == 'DeclRefExpr'
                        and decl.get('kind') == 'FunctionDecl'
                        and decl.get('name') in funcs):
                    truth.add(((source, caller), (source, decl['name'])))
    return definitions, truth, {e: 'direct' for e in truth}


def evaluate(args):
    definitions, truth, categories = reference(args)
    root = Path(args.source_root).resolve()
    byname = collections.defaultdict(list)
    for item in definitions:
        byname[item[1]].append(item)

    def normalize(file, name):
        file_path = Path(file)
        if file_path.is_absolute():
            try:
                file = str(file_path.relative_to(root))
            except ValueError:
                file = file_path.name
        candidate = (str(file), name)
        if candidate in definitions:
            return candidate
        # A header declaration and the uniquely named out-of-line definition
        # denote the same C function. Same-named static definitions retain paths.
        candidates = byname.get(name, [])
        return candidates[0] if len(candidates) == 1 else None

    predictions = {}
    details = {}
    db_path = Path(args.codegraph).resolve()
    conn = sqlite3.connect(db_path.as_uri() + '?mode=ro&immutable=1', uri=True)
    rows = conn.execute('''
        SELECT s.file_path, s.name, s.kind, t.file_path, t.name,
               e.line, e.col, e.metadata, e.provenance
        FROM edges e JOIN nodes s ON s.id=e.source JOIN nodes t ON t.id=e.target
        WHERE e.kind='calls'
    ''').fetchall()
    spans = conn.execute("SELECT file_path,name,start_line,end_line FROM nodes WHERE kind IN ('function','method')").fetchall()
    predicted = set()
    records = []
    for sf, sn, sk, tf, tn, line, col, metadata, provenance in rows:
        source = normalize(sf, sn)
        if source is None and line is not None:
            owners = [(end - start, normalize(f, n)) for f, n, start, end in spans
                      if f == sf and start <= line <= end and normalize(f, n)]
            if owners:
                source = min(owners)[1]
        target = normalize(tf, tn)
        if source is not None and target is not None:
            predicted.add((source, target))
            records.append({'caller': source, 'callee': target, 'callsite_file': sf,
                            'line': line, 'column': col,
                            'metadata': json.loads(metadata) if metadata else None,
                            'provenance': provenance})
    conn.close()
    predictions['CodeGraph'] = predicted
    details['CodeGraph'] = records

    graph = json.loads(Path(args.yasa).read_text())
    nodes = graph['nodes']
    predicted = set()
    records = []
    for edge in graph['edges'].values():
        s = nodes[edge['sourceNodeId']].get('funcDef')
        t = nodes[edge['targetNodeId']].get('funcDef')
        if not isinstance(s, dict) or not isinstance(t, dict):
            continue
        source = normalize(s['loc']['sourcefile'], s['name'])
        target = normalize(t['loc']['sourcefile'], t['name'])
        if source is not None and target is not None:
            predicted.add((source, target))
            records.append({'caller': source, 'callee': target, 'callsite': edge.get('callSite')})
    predictions['Yasa'] = predicted
    details['Yasa'] = records

    results = []
    for tool in ['Yasa', 'CodeGraph']:
        predicted = predictions[tool]
        tp = len(predicted & truth)
        fp = len(predicted - truth)
        fn = len(truth - predicted)
        result = {
            'tool': tool, 'functions': len(definitions), 'gold_edges': len(truth),
            'predicted_edges': len(predicted), 'tp': tp, 'fp': fp, 'fn': fn,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            'false_positives': sorted(predicted - truth),
            'false_negatives': sorted(truth - predicted),
            'predicted': sorted(predicted), 'truth': sorted(truth),
            'edge_records': details[tool],
            'category_recall': {
                category: {'tp': sum(e in predicted for e in truth if categories[e] == category),
                           'gold': sum(categories[e] == category for e in truth)}
                for category in sorted(set(categories.values()))
            },
        }
        results.append(result)
    Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps([{k: r[k] for k in ['tool','gold_edges','tp','fp','fn','precision','recall','f1']}
                      for r in results], ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--gold')
    group.add_argument('--clang-ast')
    parser.add_argument('--source-file')
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--yasa', required=True)
    parser.add_argument('--codegraph', required=True)
    parser.add_argument('--output', required=True)
    evaluate(parser.parse_args())
