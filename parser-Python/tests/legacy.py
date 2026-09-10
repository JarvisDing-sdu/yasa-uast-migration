"""Test-only oracle. The npm parser never invokes Python."""
import ast
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from uast.visitor import UASTTransformer
import uast.asttype as UNode

def parse(source):
    tree = ast.parse(source)
    tree.sourcefile = 'fixture.py'
    result = UASTTransformer().visit(tree)
    if '--unit' in sys.argv:
        unit = UASTTransformer().packPos(tree, UNode.CompileUnit(
            UNode.SourceLocation(), UNode.Meta(), body=result, language='python',
            uri=None, version=None, languageVersion='3.13'))
        unit.loc.sourcefile = 'fixture.py'
        return json.loads(unit.to_json())
    return [json.loads(node.to_json()) for node in result]


if '--batch' in sys.argv:
    results = []
    for source in json.load(sys.stdin):
        try:
            results.append({'body': parse(source)})
        except Exception as error:
            results.append({'error': str(error)})
    print(json.dumps(results, ensure_ascii=False))
else:
    print(json.dumps(parse(sys.stdin.read()), ensure_ascii=False))
