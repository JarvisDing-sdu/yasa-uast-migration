#!/usr/bin/env python3
"""Level 1 audit: is each new Yasa callback edge's target stored into the field called on that line (clang)?

Inputs: clang extraction (curl-field-stores.json), yasa-fixed and yasa-callback normalized records.
Output: type-level-check.json with per-edge verdicts and per-line missing targets.
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]
clang = json.loads((HERE / 'curl-field-stores.json').read_text())
old = json.loads((WORK / 'curl-large/results/yasa-fixed/normalized.json').read_text())['records']
new = json.loads((WORK / 'callback-fix/curl/results/yasa-callback/normalized.json').read_text())['records']

gold = json.loads((WORK / 'curl-large/reference/gold.json').read_text())
by_name = collections.defaultdict(list)
for d in gold['definitions']:
    by_name[d['name']].append(d['id'])


def canonical(fid):
    """A function seen only through a header prototype in its TU maps to its unique compiled definition."""
    file, _, name = fid.partition('::')
    if file.endswith('.h') and fid not in {i for ids in by_name.values() for i in ids} and len(by_name.get(name, [])) == 1:
        return by_name[name][0]
    return fid


fields_at = collections.defaultdict(set)
for file, line, field in clang['calls']:
    fields_at[(file, line)].add(field)
stores = {k: {canonical(f) for f in v} for k, v in clang['stores'].items()}

key = lambda r: (r['caller'], r['target'], r['file'], r['line'])
before = {key(r) for r in old if r['target_scope'] == 'active_internal'}
added = [r for r in new if r['target_scope'] == 'active_internal' and key(r) not in before]

verdicts = collections.Counter()
edges = []
for r in added:
    fields = fields_at.get((r['file'], r['line']), set())
    allowed = set().union(*(stores.get(f, set()) for f in fields)) if fields else set()
    v = 'no_clang_field_call_on_line' if not fields else ('target_stored_in_called_field' if r['target'] in allowed else 'target_not_stored_in_called_field')
    verdicts[v] += 1
    edges.append(dict(file=r['file'], line=r['line'], caller=r['caller'], target=r['target'], fields=sorted(fields), verdict=v))

# reverse: clang field-call lines with stored targets that Yasa (new) did not resolve on that line
resolved = collections.defaultdict(set)
for r in new:
    if r['target_scope'] == 'active_internal':
        resolved[(r['file'], r['line'])].add(r['target'])
missing = []
for (file, line), fields in sorted(fields_at.items()):
    expected = set().union(*(stores.get(f, set()) for f in fields))
    lost = sorted(expected - resolved[(file, line)])
    if lost:
        missing.append(dict(file=file, line=line, fields=sorted(fields), expected=len(expected), missing=lost))

out = dict(added_edges=len(added), verdicts=dict(verdicts), clang_field_call_lines=len(fields_at),
           lines_with_missing_targets=len(missing),
           missing_pairs=sum(len(m['missing']) for m in missing),
           expected_pairs=sum(len(set().union(*(stores.get(f, set()) for f in fs))) for fs in fields_at.values()),
           edges=edges, missing=missing)
(HERE / 'type-level-check.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k not in ('edges', 'missing')}, indent=1))
