#!/usr/bin/env python3
"""Score frozen libcurl callgraph predictions against independently frozen gold.

Rules frozen before loading analyzer predictions. The primary population is
non-macro Clang direct sites on lines containing no Clang indirect calls. All
gold definitions remain eligible regardless of either analyzer's coverage.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


SCORING_PROTOCOL = {
    'version': 1,
    'primary_population': 'Clang direct callsites without enclosing_macro_expansions or macro_origin_differs; exclude any caller/file/line containing an indirect call',
    'strict_attribution': 'exact caller, relative source file, 1-based line and column',
    'fallback_attribution': 'strict first; otherwise accept same caller/file/line only if all Clang direct observations on that line have one distinct coordinate and the line has no indirect observations',
    'internal_predictions': 'active_internal and inactive_project targets; inactive_project targets receive distinct identity even if file::name equals an active definition',
    'external_and_unresolved': 'not internal resolved predictions; missing expected internal targets remain false negatives',
    'pair_aggregation': 'deduplicate caller-target pairs only after attribution to fixed primary population',
    'full_ast_recall': 'location-free coverage of all Clang internal direct caller-target pairs; no precision because this graph can contain valid indirect edges',
    'indirect_subset': '11 analyzer-blind selected sites, 25 expected site-target edges; site-level recall and location-free caller-target recall only, no extrapolation',
}
PROTOCOL_SHA256 = hashlib.sha256(json.dumps(SCORING_PROTOCOL, sort_keys=True).encode()).hexdigest()


def site_key(call):
    return (call.get('caller'), call.get('file'), call.get('line'), call.get('column'))


def line_key(call):
    return (call.get('caller'), call.get('file'), call.get('line'))


def metric(expected, predicted):
    tp = expected & predicted
    fp = predicted - expected
    fn = expected - predicted
    p = len(tp) / len(predicted) if predicted else None
    r = len(tp) / len(expected) if expected else None
    return {
        'gold': len(expected), 'predicted': len(predicted),
        'tp': len(tp), 'fp': len(fp), 'fn': len(fn),
        'precision': p, 'recall': r,
        'f1': (2 * p * r / (p + r)) if p is not None and r is not None and p + r else (0.0 if p is not None and r is not None else None),
    }, {'false_positives': sorted(fp), 'false_negatives': sorted(fn)}


def build_frame(gold):
    direct = defaultdict(list)
    direct_lines = defaultdict(set)
    indirect_lines = {line_key(c) for c in gold['indirect_calls']}
    indirect_exact = {site_key(c) for c in gold['indirect_calls']}
    for call in gold['direct_calls']:
        direct[site_key(call)].append(call)
        direct_lines[line_key(call)].add(site_key(call))
    safe = {
        k: calls for k, calls in direct.items()
        if not any(c.get('enclosing_macro_expansions') or c.get('macro_origin_differs') for c in calls)
        and k[:3] not in indirect_lines
    }
    expected_sites = {
        (*k, c['internal_target'])
        for k, calls in safe.items() for c in calls if c.get('internal_target')
    }
    expected_pairs = {(k[0], k[4]) for k in expected_sites}
    safe_line_map = {
        k[:3]: k for k in safe if len(direct_lines[k[:3]]) == 1
    }
    return {
        'direct': direct, 'direct_lines': direct_lines,
        'indirect_lines': indirect_lines, 'indirect_exact': indirect_exact,
        'safe': safe, 'safe_line_map': safe_line_map,
        'expected_sites': expected_sites, 'expected_pairs': expected_pairs,
        'definition_ids': {d['id'] for d in gold['definitions']},
        'full_pairs': {(c['caller'], c['internal_target']) for c in gold['direct_calls'] if c.get('internal_target')},
    }


def resolved_internal_target(record, definitions):
    scope = record.get('target_scope')
    target = record.get('target')
    if scope == 'active_internal':
        if target not in definitions:
            raise ValueError(f"active_internal target not in gold definitions: {target!r}")
        return target
    if scope == 'inactive_project':
        # A platform-inactive implementation may share the active function's name.
        # Retain it as an incorrect resolved target, never credit active recall.
        return 'inactive::' + str(target or record.get('raw_id') or '<unknown>')
    if scope not in ('external', 'unresolved'):
        raise ValueError(f'Unknown target_scope: {scope!r}')
    return None


def attribute(record, frame, fallback=False):
    k = site_key(record)
    if k in frame['safe']:
        return k, 'strict'
    if fallback and k[:3] in frame['safe_line_map']:
        return frame['safe_line_map'][k[:3]], 'single_coordinate_line_fallback'
    if not record.get('caller'):
        return None, 'unmapped_caller'
    if not record.get('file') or not record.get('line'):
        return None, 'missing_location'
    if k[:3] in frame['indirect_lines']:
        return None, 'line_with_indirect_calls'
    if k in frame['direct']:
        return None, 'excluded_macro_direct_coordinate'
    if k[:3] in frame['direct_lines']:
        return None, 'direct_line_but_unmatched_coordinate'
    return None, 'no_compiler_direct_line'


def score_primary(records, frame, fallback=False):
    predicted = set()
    emitted_points = set()
    resolved_points = set()
    attribution = Counter()
    attributed_scopes = Counter()
    details = defaultdict(list)
    for record in records:
        target = resolved_internal_target(record, frame['definition_ids'])
        k, reason = attribute(record, frame, fallback)
        attribution[reason] += 1
        if k is None:
            continue
        emitted_points.add(k)
        attributed_scopes[record['target_scope']] += 1
        if target is not None:
            edge = (*k, target)
            predicted.add(edge)
            resolved_points.add(k)
            details[edge].append(record.get('raw_id'))
    pairs = {(e[0], e[4]) for e in predicted}
    sites_metric, sites_mismatches = metric(frame['expected_sites'], predicted)
    pair_metric, pair_mismatches = metric(frame['expected_pairs'], pairs)
    expected_internal_points = {e[:4] for e in frame['expected_sites']}
    metrics = {
        'callsite_target': sites_metric,
        'function_pair': pair_metric,
        'emitted_callsite_coverage': {
            'all_primary_points_with_any_record': len(emitted_points),
            'internal_gold_points_with_any_record': len(emitted_points & expected_internal_points),
            'internal_gold_points_with_internal_resolution': len(resolved_points & expected_internal_points),
            'primary_points_with_internal_resolution': len(resolved_points),
        },
        'record_attribution': dict(attribution),
        'attributed_record_target_scopes': dict(attributed_scopes),
    }
    mismatches = {
        'callsite_target': sites_mismatches,
        'function_pair': pair_mismatches,
        'false_positive_raw_ids': [
            {'edge': e, 'raw_ids': details[e]}
            for e in sorted(predicted - frame['expected_sites'])
        ],
    }
    return metrics, mismatches


def score_indirect(records, frame, curated):
    expected_site_edges = set()
    expected_pairs = set()
    site_id_by_key = {}
    for s in curated['sites']:
        k = (s['caller'], s['caller_file'], s['callsite']['line'], s['callsite']['column'])
        site_id_by_key[k] = s['id']
        for target in s['expected_targets']:
            expected_site_edges.add((*k, target['id']))
            expected_pairs.add((k[0], target['id']))
    indirect_lines = defaultdict(set)
    for c in frame['indirect_exact']:
        indirect_lines[c[:3]].add(c)
    fallback_by_line = {
        k[:3]: k for k in site_id_by_key
        if len(indirect_lines[k[:3]]) == 1 and k[:3] not in frame['direct_lines']
    }
    strict = set()
    fallback = set()
    pairs = set()
    for record in records:
        if record.get('target_scope') != 'active_internal':
            continue
        target = resolved_internal_target(record, frame['definition_ids'])
        pairs.add((record.get('caller'), target))
        k = site_key(record)
        if k in site_id_by_key:
            strict.add((*k, target))
            fallback.add((*k, target))
        elif k[:3] in fallback_by_line:
            fallback.add((*fallback_by_line[k[:3]], target))
    def recall(expected, actual):
        found = expected & actual
        return {'gold': len(expected), 'found': len(found), 'missing': len(expected - actual), 'recall': len(found) / len(expected) if expected else None}
    result = {
        'label': 'curated_indirect_subset_recall_only',
        'selected_sites': len(site_id_by_key),
        'strict_site_target': recall(expected_site_edges, strict),
        'single_coordinate_line_fallback_site_target': recall(expected_site_edges, fallback),
        'location_free_caller_target': recall(expected_pairs, pairs),
        'per_site': [],
    }
    for k, id_ in site_id_by_key.items():
        expected = {e[4] for e in expected_site_edges if e[:4] == k}
        strict_targets = {e[4] for e in strict if e[:4] == k}
        fallback_targets = {e[4] for e in fallback if e[:4] == k}
        pair_targets = {t for c, t in pairs if c == k[0]}
        result['per_site'].append({
            'id': id_, 'site': k, 'expected_targets': sorted(expected),
            'strict_found': sorted(expected & strict_targets),
            'fallback_found': sorted(expected & fallback_targets),
            'caller_pair_found': sorted(expected & pair_targets),
        })
    return result, {
        'strict_missing': sorted(expected_site_edges - strict),
        'fallback_missing': sorted(expected_site_edges - fallback),
        'caller_pair_missing': sorted(expected_pairs - pairs),
    }


def score_tool(normalized, frame, curated):
    records = normalized['records']
    strict, strict_errors = score_primary(records, frame)
    fallback, fallback_errors = score_primary(records, frame, fallback=True)
    observed_functions = set(normalized['functions'])
    graph_pairs = {
        (r.get('caller'), resolved_internal_target(r, frame['definition_ids']))
        for r in records if r.get('target_scope') == 'active_internal'
    }
    full_found = frame['full_pairs'] & graph_pairs
    indirect, indirect_errors = score_indirect(records, frame, curated)
    result = {
        'tool': normalized['tool'], 'raw_records': len(records),
        'record_target_scopes': dict(Counter(r['target_scope'] for r in records)),
        'definition_coverage': {
            'gold': len(frame['definition_ids']),
            'active_definitions_found': len(observed_functions & frame['definition_ids']),
            'recall': len(observed_functions & frame['definition_ids']) / len(frame['definition_ids']),
            'unknown_function_ids_in_normalized_functions': sorted(observed_functions - frame['definition_ids']),
        },
        'primary_strict': strict,
        'primary_single_coordinate_line_fallback': fallback,
        'full_ast_direct_pair_recall': {
            'gold': len(frame['full_pairs']), 'found': len(full_found),
            'missing': len(frame['full_pairs'] - graph_pairs),
            'recall': len(full_found) / len(frame['full_pairs']),
            'precision': None,
            'note': 'Clang syntactic AST includes macros, compile-time checking helpers and path-infeasible branches; this supplementary measure does not assert runtime reachability.',
        },
        'curated_indirect': indirect,
        'normalization_metadata': normalized.get('metadata', {}),
    }
    errors = {
        'primary_strict': strict_errors,
        'primary_single_coordinate_line_fallback': fallback_errors,
        'full_ast_direct_pair_missing': sorted(frame['full_pairs'] - graph_pairs),
        'missing_active_definitions': sorted(frame['definition_ids'] - observed_functions),
        'curated_indirect': indirect_errors,
    }
    return result, errors


def self_test():
    def call(col, target, macro=False, line=10):
        return dict(caller='a.c::a', file='a.c', line=line, column=col,
                    internal_target=target, enclosing_macro_expansions=[{}] if macro else [], macro_origin_differs=False)
    gold = dict(definitions=[{'id': x} for x in ['a.c::a', 'b.c::b', 'c.c::c']],
                direct_calls=[call(3, 'b.c::b'), call(7, None, line=12), call(3, 'c.c::c', macro=True, line=20), call(3, 'c.c::c', line=30)],
                indirect_calls=[dict(caller='a.c::a', file='a.c', line=30, column=20)])
    frame = build_frame(gold)
    assert len(frame['safe']) == 2 and len(frame['expected_pairs']) == 1
    def rec(col, target, scope='active_internal', line=10):
        return dict(caller='a.c::a', file='a.c', line=line, column=col, target=target, target_scope=scope, raw_id=f'{col}-{target}-{scope}')
    records = [rec(3, 'b.c::b'), rec(3, 'b.c::b'), rec(3, 'b.c::b', 'inactive_project'),
               rec(3, None, 'unresolved'), rec(9, 'c.c::c'), rec(7, 'c.c::c', line=12), rec(3, 'c.c::c', line=20)]
    strict, _ = score_primary(records, frame)
    fallback, _ = score_primary(records, frame, True)
    assert strict['callsite_target']['tp'] == 1
    assert strict['callsite_target']['fp'] == 2
    assert strict['function_pair']['fp'] == 2
    assert fallback['callsite_target']['tp'] == 1 and fallback['callsite_target']['fp'] == 3
    assert fallback['function_pair']['fp'] == 2  # same wrong pair at two sites is deduplicated
    assert metric({1}, set())[0]['precision'] is None
    print('Self-test PASS: fixed population, macro/indirect exclusion, wrong targets, inactive same-name identity, deduplication, strict/fallback, undefined precision.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    base = Path(__file__).resolve().parent
    gold_path = base / 'reference/gold.json'
    curated_path = base / 'indirect-audit/indirect-gold.json'
    gold = json.loads(gold_path.read_text())
    curated = json.loads(curated_path.read_text())
    frame = build_frame(gold)
    scores = {
        'scoring_protocol': SCORING_PROTOCOL,
        'scoring_protocol_sha256': PROTOCOL_SHA256,
        'gold_sha256': hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        'curated_gold_sha256': hashlib.sha256(curated_path.read_bytes()).hexdigest(),
        'population': {
            'all_definitions': len(frame['definition_ids']),
            'all_direct_internal_pairs': len(frame['full_pairs']),
            'all_direct_unique_coordinates': len(frame['direct']),
            'primary_direct_coordinates': len(frame['safe']),
            'primary_internal_coordinates': len({e[:4] for e in frame['expected_sites']}),
            'primary_internal_site_target_edges': len(frame['expected_sites']),
            'primary_internal_pairs': len(frame['expected_pairs']),
            'primary_external_coordinates': sum(not any(c.get('internal_target') for c in cs) for cs in frame['safe'].values()),
            'primary_internal_pair_coverage_of_full_ast': len(frame['expected_pairs']) / len(frame['full_pairs']),
            'fallback_eligible_primary_lines': len(frame['safe_line_map']),
            'mixed_direct_indirect_lines': len(frame['direct_lines'].keys() & frame['indirect_lines']),
            'mixed_direct_indirect_exact_coordinates': len(frame['direct'].keys() & frame['indirect_exact']),
        },
        'tools': {},
    }
    errors = {'scoring_protocol_sha256': PROTOCOL_SHA256, 'tools': {}}
    for tool in ('yasa', 'codegraph'):
        p = base / 'results' / tool / 'normalized.json'
        normalized = json.loads(p.read_text())
        result, tool_errors = score_tool(normalized, frame, curated)
        result['normalized_sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        scores['tools'][tool] = result
        errors['tools'][tool] = tool_errors
    results = base / 'results'
    (results / 'scores.json').write_text(json.dumps(scores, indent=2) + '\n')
    (results / 'mismatches.json').write_text(json.dumps(errors, indent=2) + '\n')
    print(json.dumps({'population': scores['population'], 'tools': {
        tool: {k: v for k, v in score.items() if k in ('definition_coverage', 'primary_strict', 'primary_single_coordinate_line_fallback', 'full_ast_direct_pair_recall', 'curated_indirect')}
        for tool, score in scores['tools'].items()
    }}, indent=2))


if __name__ == '__main__':
    main()
