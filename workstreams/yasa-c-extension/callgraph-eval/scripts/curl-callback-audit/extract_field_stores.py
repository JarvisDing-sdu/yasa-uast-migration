#!/usr/bin/env python3
"""Independent clang extraction of function-pointer field stores and field-call sites.

Reads no analyzer output. For every translation unit in a compile database:
- stores: (record, field) <- function, from `x.f = fn` / `x->f = &fn` assignments and
  from initializer lists (clang's semantic form maps positional and designated values to fields);
- calls: call expressions whose callee is a function-pointer field, with the (record, field).
Run with PYTHONPATH=curl-large/tooling/python.

Usage: extract_field_stores.py <compile_commands.json> <source_root> <out.json>
"""
import json
import shlex
import sys
from pathlib import Path

from clang import cindex

LIBCLANG = '/Library/Developer/CommandLineTools/usr/lib/libclang.dylib'
K = cindex.CursorKind


def record_name(t):
    """Name of the struct/union behind a type (through typedefs, pointers, const)."""
    t = t.get_canonical()
    while t.kind == cindex.TypeKind.POINTER:
        t = t.get_pointee().get_canonical()
    decl = t.get_declaration()
    if decl.kind in (K.STRUCT_DECL, K.UNION_DECL):
        return decl.spelling or decl.type.spelling
    return None


def function_of(expr):
    """FunctionDecl referenced by an expression, looking through casts, parens and `&`."""
    node = expr
    for _ in range(16):
        if node is None:
            return None
        if node.kind == K.DECL_REF_EXPR:
            ref = node.referenced
            return ref if ref is not None and ref.kind == K.FUNCTION_DECL else None
        children = list(node.get_children())
        if node.kind in (K.UNEXPOSED_EXPR, K.PAREN_EXPR, K.CSTYLE_CAST_EXPR, K.UNARY_OPERATOR) and len(children) == 1:
            node = children[0]
            continue
        return None
    return None


def field_of(member_ref):
    ref = member_ref.referenced
    if ref is None or ref.kind != K.FIELD_DECL:
        return None
    rec = ref.semantic_parent
    return (rec.spelling or rec.type.spelling, ref.spelling) if rec is not None else None


def rel(path, root):
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def fn_id(decl, root):
    d = decl.get_definition() or decl
    return f'{rel(d.location.file.name, root)}::{d.spelling}' if d.location.file else d.spelling


def walk_init(init, rtype, root, stores):
    """Map an INIT_LIST_EXPR's values to fields (semantic form is positional over all fields)."""
    canonical = rtype.get_canonical()
    if canonical.kind in (cindex.TypeKind.CONSTANTARRAY, cindex.TypeKind.INCOMPLETEARRAY):
        for child in init.get_children():
            if child.kind == K.INIT_LIST_EXPR:
                walk_init(child, canonical.element_type, root, stores)
        return
    decl = canonical.get_declaration()
    if decl.kind not in (K.STRUCT_DECL, K.UNION_DECL):
        return
    fields = [f for f in decl.get_children() if f.kind == K.FIELD_DECL]
    rec = decl.spelling or decl.type.spelling
    for field, value in zip(fields, init.get_children()):
        if value.kind == K.INIT_LIST_EXPR:
            walk_init(value, field.type, root, stores)
            continue
        fn = function_of(value)
        if fn is not None:
            stores.setdefault(f'{rec}.{field.spelling}', set()).add(fn_id(fn, root))


def scan(tu, root, stores, calls):
    for node in tu.cursor.walk_preorder():
        loc = node.location
        if loc.file is None:
            continue
        if node.kind == K.BINARY_OPERATOR:
            kids = list(node.get_children())
            # operator kind, not tokens: macro-expanded assignments have no tokens
            if len(kids) == 2 and kids[0].kind == K.MEMBER_REF_EXPR and node.binary_operator == cindex.BinaryOperator.Assign:
                field = field_of(kids[0])
                fn = function_of(kids[1])
                if field and fn is not None:
                    stores.setdefault(f'{field[0]}.{field[1]}', set()).add(fn_id(fn, root))
        elif node.kind == K.VAR_DECL:
            for child in node.get_children():
                if child.kind == K.INIT_LIST_EXPR:
                    walk_init(child, node.type, root, stores)
        elif node.kind == K.CALL_EXPR:
            kids = list(node.get_children())
            if not kids:
                continue
            callee = kids[0]
            for _ in range(8):
                inner = list(callee.get_children())
                if callee.kind in (K.UNEXPOSED_EXPR, K.PAREN_EXPR, K.UNARY_OPERATOR) and len(inner) == 1:
                    callee = inner[0]
                else:
                    break
            if callee.kind == K.MEMBER_REF_EXPR:
                field = field_of(callee)
                if field:
                    # expansion location: the line the analyzer sees in the source file
                    f, line, col, _ = loc.file, loc.line, loc.column, None
                    calls.add((rel(f.name, root), line, f'{field[0]}.{field[1]}'))


def main():
    db_path, source_root, out_path = sys.argv[1:4]
    cindex.Config.set_library_file(LIBCLANG)
    cindex.Config.set_compatibility_check(False)
    root = Path(source_root).resolve()
    index = cindex.Index.create()
    stores, calls, failed = {}, set(), []
    for entry in json.load(open(db_path)):
        args = shlex.split(entry['command']) if 'command' in entry else list(entry['arguments'])
        args = [a for a in args[1:] if a not in ('-c',)]
        if '-o' in args:
            i = args.index('-o')
            del args[i:i + 2]
        src = entry['file']
        args = [a for a in args if a != src]
        try:
            tu = index.parse(src, args=args, options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
        except cindex.TranslationUnitLoadError:
            failed.append(src)
            continue
        errors = [d for d in tu.diagnostics if d.severity >= cindex.Diagnostic.Error]
        if errors:
            failed.append(src)
        scan(tu, root, stores, calls)
    out = dict(stores={k: sorted(v) for k, v in sorted(stores.items())},
               calls=sorted([list(c) for c in calls]),
               translation_units=len(json.load(open(db_path))), failed=failed)
    Path(out_path).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(dict(stores=len(out['stores']), calls=len(out['calls']), failed=failed)))


if __name__ == '__main__':
    main()
