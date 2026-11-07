#!/usr/bin/env python3
"""Extract compiler-resolved C definitions and call sites without analyzer input.

Run with PYTHONPATH=../tooling/python and Apple's libclang. The compile database
defines the entire eligible source population. External direct calls are retained
for callsite classification; only calls to actual compiled project definitions
enter direct_edges. Function-pointer calls are recorded, never guessed here.
"""
import argparse
import ctypes
import hashlib
import json
import itertools
import multiprocessing
import os
from pathlib import Path
import shlex
import subprocess
import time

from clang import cindex

LIBCLANG = "/Library/Developer/CommandLineTools/usr/lib/libclang.dylib"


def setup_clang():
    if cindex.Config.loaded:
        return
    cindex.Config.set_library_file(LIBCLANG)
    cindex.Config.set_compatibility_check(False)
    for name in ("clang_getExpansionLocation", "clang_getSpellingLocation"):
        function = getattr(cindex.conf.lib, name)
        function.argtypes = [cindex.SourceLocation, ctypes.POINTER(cindex.c_object_p),
                            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
                            ctypes.POINTER(ctypes.c_uint)]
        function.restype = None


def canonical_file(filename, source, build):
    if not filename:
        return None
    p = Path(filename).resolve()
    try:
        rel = p.relative_to(source)
        if rel.parts and rel.parts[0] in ("lib", "include"):
            return rel.as_posix()
    except ValueError:
        pass
    try:
        return "@generated/" + p.relative_to(build).as_posix()
    except ValueError:
        return str(p)


def is_project(filename):
    return bool(filename) and filename.startswith(("lib/", "include/", "@generated/"))


def location_info(loc, source, build, function):
    file_pointer = cindex.c_object_p()
    line = ctypes.c_uint()
    column = ctypes.c_uint()
    offset = ctypes.c_uint()
    getattr(cindex.conf.lib, function)(
        loc, ctypes.byref(file_pointer), ctypes.byref(line),
        ctypes.byref(column), ctypes.byref(offset))
    filename = cindex.File(file_pointer).name if file_pointer else None
    return {"file": canonical_file(filename, source, build), "line": line.value,
            "column": column.value, "offset": offset.value}


def site_info(cursor, source, build, tu_file):
    expansion = location_info(cursor.location, source, build, "clang_getExpansionLocation")
    spelling = location_info(cursor.location, source, build, "clang_getSpellingLocation")
    return {"file": expansion["file"], "line": expansion["line"],
            "column": expansion["column"], "offset": expansion["offset"],
            "spelling": spelling, "expansion": expansion,
            "macro_origin_differs": spelling != expansion,
            "translation_unit": tu_file}


def parse_arguments(entry):
    command = entry.get("arguments") or shlex.split(entry["command"])
    # The driver executable, output artifact and source operand are supplied by
    # the C API. All semantic compile flags are otherwise preserved verbatim.
    args = []
    skip_next = False
    source_path = str(Path(entry["file"]).resolve())
    for arg in command[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg in ("-o", "-MF", "-MT", "-MQ"):
            skip_next = True
            continue
        if arg in ("-c", "-MD", "-MMD", "-MP"):
            continue
        if not arg.startswith("-"):
            candidate = Path(arg)
            if not candidate.is_absolute():
                candidate = Path(entry["directory"]) / candidate
            if str(candidate.resolve()) == source_path:
                continue
        args.append(arg)
    return args


def parse_one(task):
    entry, source_string, build_string = task
    setup_clang()
    source, build = Path(source_string), Path(build_string)
    file = str(Path(entry["file"]).resolve())
    tu_file = canonical_file(file, source, build)
    args = parse_arguments(entry)
    os.chdir(entry["directory"])
    started = time.time()
    result = {"translation_unit": tu_file, "arguments": args, "directory": entry["directory"],
              "definitions": [], "calls": [], "diagnostics": [], "failure": None}
    try:
        index = cindex.Index.create()
        tu = index.parse(file, args=args, options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
        for diagnostic in tu.diagnostics:
            result["diagnostics"].append({"severity": diagnostic.severity, "text": str(diagnostic)})
        if any(d["severity"] >= cindex.Diagnostic.Error for d in result["diagnostics"]):
            result["failure"] = "compiler diagnostics contain errors"

        macro_expansions = {}
        for macro in tu.cursor.get_children():
            if macro.kind != cindex.CursorKind.MACRO_INSTANTIATION:
                continue
            start = location_info(macro.extent.start, source, build, "clang_getExpansionLocation")
            if not is_project(start["file"]):
                continue
            end = location_info(macro.extent.end, source, build, "clang_getExpansionLocation")
            reference = macro.referenced
            definition = (location_info(reference.location, source, build, "clang_getSpellingLocation")
                          if reference else None)
            record = {"name": macro.spelling, "file": start["file"], "line": start["line"],
                      "column": start["column"], "start_offset": start["offset"],
                      "end_offset": end["offset"], "end_line": end["line"],
                      "definition": definition}
            macro_expansions.setdefault(start["file"], []).append(record)

        def walk_body(cursor, caller):
            if cursor.kind == cindex.CursorKind.CALL_EXPR:
                reference = cursor.referenced
                record = site_info(cursor, source, build, tu_file)
                record["caller"] = caller
                record["enclosing_macro_expansions"] = [macro for macro in macro_expansions.get(record["file"], [])
                    if macro["start_offset"] <= record["offset"] < macro["end_offset"]]
                try:
                    record["expression"] = " ".join(t.spelling for t in itertools.islice(cursor.get_tokens(), 150))[:1000]
                except Exception:
                    record["expression"] = cursor.spelling
                record["kind"] = "direct" if reference and reference.kind == cindex.CursorKind.FUNCTION_DECL else "indirect"
                if reference:
                    record["referenced_kind"] = reference.kind.name
                    record["referenced_name"] = reference.spelling
                    record["referenced_usr"] = reference.get_usr()
                    record["referenced_file"] = canonical_file(reference.location.file.name if reference.location.file else None, source, build)
                else:
                    record["referenced_kind"] = None
                    record["referenced_name"] = None
                    record["referenced_usr"] = None
                    record["referenced_file"] = None
                result["calls"].append(record)
            for child in cursor.get_children():
                walk_body(child, caller)

        for cursor in tu.cursor.get_children():
            if cursor.kind != cindex.CursorKind.FUNCTION_DECL or not cursor.is_definition():
                continue
            filename = canonical_file(cursor.location.file.name if cursor.location.file else None, source, build)
            if not is_project(filename):
                continue
            identifier = filename + "::" + cursor.spelling
            result["definitions"].append({"id": identifier, "file": filename, "name": cursor.spelling,
                "line": cursor.location.line, "end_line": cursor.extent.end.line,
                "column": cursor.location.column, "storage": cursor.storage_class.name,
                "linkage": cursor.linkage.name, "usr": cursor.get_usr(),
                "translation_units": [tu_file]})
            walk_body(cursor, identifier)
    except Exception as error:
        result["failure"] = repr(error)
    result["seconds"] = round(time.time() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    source, build, output = (Path(value).resolve() for value in (args.source, args.build, args.output))
    output.mkdir(parents=True, exist_ok=True)
    database = json.loads((build / "compile_commands.json").read_text())
    entries = [entry for entry in database if Path(entry["file"]).suffix == ".c"
               and Path(entry["file"]).resolve().is_relative_to(source / "lib")]
    if len({str(Path(entry["file"]).resolve()) for entry in entries}) != len(entries):
        raise RuntimeError("multiple compile commands for one source: select the declared libcurl target explicitly")
    tasks = [(entry, str(source), str(build)) for entry in entries]
    results = []
    started = time.time()
    with multiprocessing.Pool(args.jobs) as pool:
        for result in pool.imap_unordered(parse_one, tasks):
            results.append(result)
            print(json.dumps({"translation_unit": result["translation_unit"], "failure": result["failure"],
                  "definitions": len(result["definitions"]), "calls": len(result["calls"]),
                  "seconds": result["seconds"]}), flush=True)
    results.sort(key=lambda result: result["translation_unit"])
    (output / "translation-unit-results.json").write_text(json.dumps(results, indent=2) + "\n")
    definitions = {}
    usrs = {}
    for result in results:
        for definition in result["definitions"]:
            identifier = definition["id"]
            if identifier in definitions:
                existing = definitions[identifier]
                if (existing["line"], existing["end_line"]) != (definition["line"], definition["end_line"]):
                    raise RuntimeError("ambiguous canonical definition: " + identifier)
                existing["translation_units"] = sorted(set(existing["translation_units"] + definition["translation_units"]))
            else:
                definitions[identifier] = definition.copy()
            usr = definition["usr"]
            if usr in usrs and usrs[usr] != identifier:
                raise RuntimeError("multiple compiled definitions for USR: " + usr)
            usrs[usr] = identifier
    direct_calls, indirect_calls, edges = [], [], {}
    for result in results:
        for record in result["calls"]:
            if record["kind"] == "direct":
                target = usrs.get(record["referenced_usr"])
                record["internal_target"] = target
                direct_calls.append(record)
                if target:
                    key = (record["caller"], target)
                    site = {k: v for k, v in record.items() if k not in ("caller", "kind", "internal_target")}
                    edges.setdefault(key, []).append(site)
            else:
                indirect_calls.append(record)
    failures = [{"translation_unit": result["translation_unit"], "failure": result["failure"]}
                for result in results if result["failure"]]
    all_calls_sort = lambda record: (record["caller"], record["file"] or "", record["line"], record["column"], record["translation_unit"])
    direct_calls.sort(key=all_calls_sort)
    indirect_calls.sort(key=all_calls_sort)
    gold = {"metadata": {
        "method": "Apple libclang C API AST; independent of both analyzers; direct targets resolved by Clang USR to all compiled project definitions",
        "source": str(source), "build": str(build), "source_commit": subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip(),
        "libclang": LIBCLANG, "python_clang_bindings": "21.1.7", "eligible_translation_units": len(entries),
        "successfully_parsed_translation_units": len(results) - len(failures), "parse_failures": failures,
        "full_project_reference": not failures and len(results) == len(entries),
        "scope": "All compiled libcurl target C translation units plus function definitions in curl lib/include and generated project headers. External dependencies/system definitions excluded from internal edges.",
        "canonical_ids": "source-root-relative lib/... or include/... file::function-name; generated headers use @generated/...; static function file identities retained",
        "header_aggregation": "Same defining header and function name aggregate across translation units, retaining each callsite's translation_unit",
        "direct_definition": "CALL_EXPR whose referenced cursor is FUNCTION_DECL, including compiler-resolved macro calls; function-pointer referenced variables/fields are indirect",
        "pair_aggregation": "direct_edges are unique caller/callee pairs; sites retain all translation-unit observations, including repeated header bodies",
        "callsite_locations": "file/line/column are Clang expansion locations; spelling and expansion preserve macro origin when available. enclosing_macro_expansions uses Clang detailed preprocessing cursors and attaches defining macro locations when the call expansion lies in a macro invocation extent; a false macro_origin_differs does not prove the absence of a macro.",
        "definition_count": len(definitions), "direct_pair_count": len(edges),
        "direct_call_observations": len(direct_calls),
        "internal_direct_call_observations": sum(call["internal_target"] is not None for call in direct_calls),
        "external_or_uncompiled_direct_call_observations": sum(call["internal_target"] is None for call in direct_calls),
        "indirect_call_observations": len(indirect_calls), "elapsed_seconds": round(time.time() - started, 3),
        "compile_database_sha256": hashlib.sha256((build / "compile_commands.json").read_bytes()).hexdigest(),
        "extractor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }, "definitions": sorted(definitions.values(), key=lambda definition: definition["id"]),
       "direct_edges": [{"caller": caller, "callee": callee, "sites": sites} for (caller, callee), sites in sorted(edges.items())],
       "direct_calls": direct_calls, "indirect_calls": indirect_calls}
    (output / "gold.json").write_text(json.dumps(gold, indent=2) + "\n")
    (output / "summary.json").write_text(json.dumps(gold["metadata"], indent=2) + "\n")
    print(json.dumps(gold["metadata"], indent=2), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
