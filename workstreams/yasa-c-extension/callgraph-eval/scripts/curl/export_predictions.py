#!/usr/bin/env python3
"""Normalize native graph representations, retaining abstentions and inactive nodes.

Identities are file-aware. Prototype remapping to a different file is restricted
to unique externally linked compiled functions. Same-named bodies in inactive
preprocessor branches remain separate, using their definition spans.
"""
import collections
import json
from pathlib import Path
import re
import sqlite3
import sys

BASE = Path(__file__).resolve().parent
INPUT = BASE / 'input'
GOLD = json.loads((BASE / 'reference/gold.json').read_text())
DEFS = {d['id']: d for d in GOLD['definitions']}
BY_NAME = collections.defaultdict(list)
BY_FILE = collections.defaultdict(list)
for d in DEFS.values():
    BY_NAME[d['name']].append(d)
    BY_FILE[d['file']].append(d)
TEXT = {}


def relative(path):
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        for root in (INPUT, Path(GOLD['metadata']['source'])):
            try:
                return p.relative_to(root).as_posix()
            except ValueError:
                pass
        return p.as_posix()
    return p.as_posix().removeprefix('./')


def snippet(file, start, end):
    if not file or not start:
        return ''
    if file not in TEXT:
        try:
            TEXT[file] = (INPUT / file).read_text(errors='replace').splitlines()
        except (OSError, ValueError):
            TEXT[file] = []
    return '\n'.join(TEXT[file][start - 1:end or start])


def identity(file, name, start=None, end=None, kind='function', declared_static=False):
    file = relative(file)
    if not file or not name or kind not in ('function', 'method'):
        return None, 'unresolved', 'not_function_definition'
    candidate = file + '::' + name
    text = snippet(file, start, end)
    # Both tools emit function declaration nodes as well as body nodes. A
    # declaration may denote a compiled definition elsewhere; an inactive body
    # must never be credited just because its name matches.
    body = '{' in re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    active = DEFS.get(candidate)
    if active:
        overlap = bool(start and end and start <= active['end_line'] and end >= active['line'])
        if overlap or (not body and start):
            return candidate, 'active_internal', 'same_file_active_span' if overlap else 'same_file_prototype'
        return candidate + '@inactive:' + str(start), 'inactive_project', 'same_name_inactive_body'
    if not body and start and not declared_static and not re.search(r'\bstatic\b', text):
        global_defs = [d for d in BY_NAME.get(name, []) if d['linkage'] == 'EXTERNAL']
        if len(global_defs) == 1:
            return global_defs[0]['id'], 'active_internal', 'unique_external_prototype'
    if not Path(file).is_absolute() and (INPUT / file).is_file():
        # A real body in an inactive branch is still a project target and can
        # be a false positive when emitted at an active direct-call site.
        if body:
            return candidate + '@inactive:' + str(start), 'inactive_project', 'uncompiled_project_body'
        return candidate, 'external', 'uncompiled_project_declaration'
    return candidate, 'external', 'external_function'


def export_yasa(variant='yasa'):
    folder = BASE / 'results' / variant
    files = list((folder / 'report').rglob('callgraph.json'))
    if len(files) != 1:
        raise RuntimeError(f'Expected one callgraph.json, got {files}')
    graph = json.loads(files[0].read_text())
    normalized = {}
    reasons = collections.Counter()
    functions = set()
    for key, n in graph['nodes'].items():
        d = n.get('funcDef')
        if isinstance(d, dict):
            loc = d.get('loc', {})
            val = identity(loc.get('sourcefile'), d.get('name'),
                           loc.get('start', {}).get('line'), loc.get('end', {}).get('line'))
        else:
            val = (None, 'unresolved', 'placeholder')
        normalized[key] = val
        reasons[val[2]] += 1
        if val[1] == 'active_internal' and val[2] == 'same_file_active_span':
            functions.add(val[0])
    records = []
    for edge in graph['edges'].values():
        caller, caller_scope, cr = normalized[edge['sourceNodeId']]
        target, scope, tr = normalized[edge['targetNodeId']]
        loc = (edge.get('callSite') or {}).get('loc') or {}
        pos = loc.get('start') or {}
        records.append(dict(caller=caller, caller_scope=caller_scope, target=target,
                            target_scope=scope, file=relative(loc.get('sourcefile')),
                            line=pos.get('line'), column=pos.get('column'),
                            raw_id=edge.get('id'), caller_normalization=cr,
                            target_normalization=tr, raw_target=edge['targetNodeId']))
    return dict(tool=variant, functions=sorted(functions), records=records,
                metadata=dict(source_graph=str(files[0]), raw_nodes=len(graph['nodes']),
                              raw_edges=len(graph['edges']), node_mapping_reasons=dict(reasons),
                              column_convention='Native 1-based, calibrated on independent small C example.'))


def export_codegraph():
    path = (INPUT / '.codegraph/codegraph.db').resolve()
    db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    db.row_factory = sqlite3.Row
    nodes = {n['id']: dict(n) for n in db.execute('SELECT * FROM nodes')}
    normalized = {}
    reasons = collections.Counter()
    functions = set()
    for key, n in nodes.items():
        val = identity(n['file_path'], n['name'], n['start_line'], n['end_line'], n['kind'], bool(n['is_static']))
        normalized[key] = val
        reasons[val[2]] += 1
        if val[1] == 'active_internal' and val[2] == 'same_file_active_span':
            functions.add(val[0])
    records = []
    for edge in db.execute("SELECT * FROM edges WHERE kind='calls'"):
        s, t = nodes[edge['source']], nodes[edge['target']]
        caller, cs, cr = normalized[edge['source']]
        target, scope, tr = normalized[edge['target']]
        file = relative(s['file_path'])
        # CodeGraph sometimes attaches a call to a local variable node. The
        # source representation then names a lexical binding, not its enclosing
        # procedure. Recover that procedure from CodeGraph's own function spans.
        # Never repair a different function node or a wrong target.
        if s['kind'] not in ('function', 'method') and edge['line']:
            owners = [n for n in nodes.values() if n['kind'] in ('function', 'method')
                      and relative(n['file_path']) == file
                      and n['start_line'] <= edge['line'] <= n['end_line']]
            if owners:
                owner = min(owners, key=lambda n: n['end_line'] - n['start_line'])
                caller, cs, _ = normalized[owner['id']]
                cr = 'lexical_owner_of_nonfunction_source'
        records.append(dict(caller=caller, caller_scope=cs, target=target, target_scope=scope,
                            file=file, line=edge['line'], column=(edge['col'] + 1 if edge['col'] is not None else None),
                            raw_id=edge['id'], caller_normalization=cr, target_normalization=tr,
                            raw_source_kind=s['kind'], raw_source=s['name'], raw_target=t['name'],
                            provenance=edge['provenance']))
    db.close()
    return dict(tool='codegraph', functions=sorted(functions), records=records,
                metadata=dict(source_database=str(path), raw_nodes=len(nodes), raw_edges=len(records),
                              node_mapping_reasons=dict(reasons),
                              lexical_source_repairs=sum(r['caller_normalization'] == 'lexical_owner_of_nonfunction_source' for r in records),
                              column_convention='Native 0-based plus 1, calibrated on independent small C example.'))


if __name__ == '__main__':
    tool = sys.argv[1]
    out = export_yasa(tool) if tool in ('yasa', 'yasa-fixed') else export_codegraph()
    dest = BASE / 'results' / tool / 'normalized.json'
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'records'}, ensure_ascii=False)[:2000])
