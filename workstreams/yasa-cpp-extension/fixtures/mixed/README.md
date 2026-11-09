# Mixed scanner CLI acceptance fixtures

`gold.json` was frozen before the first executable new-mode acceptance run. It
contains the complete case denominator, labels, per-domain source membership,
expected call edges, original source/sink locations, trace files, and SHA256 of
every fixture input. The test independently computes compilation entry IDs with
Node crypto; it imports no production ID, parser, or runner helpers.

Run from `engine`:

```text
node --import tsx node_modules/mocha/bin/mocha test/c-family/test-mixed-cli.ts
```

The public scanner command exercised by each case is:

```text
node --import tsx src/main.ts --sourcePath DIR --language c-cpp --compileCommands FILE --buildProfile FILE --report NEW_DIR [--dumpAllCG]
```

The suite copies each frozen case to a fresh temporary directory, invokes the
exact compiler arguments recorded in its compilation database, and separately
links each program/domain with Clang++. Object files, binaries, databases,
profiles, and reports have unique paths. It never runs the linked binaries and
never invokes a shell. Missing compilers fail setup; no fixture is skipped.
`cpp_to_c_T` and `cpp_to_c_F` also exercise `--dumpAllCG`.

Every successful scan requires exit 0, exactly the selected unit IDs/domains/files,
terminal `analyzed` statuses, explicit diagnostics, nonzero analyzed entrypoints,
and a valid SARIF run. A positive requires a `system` finding at the frozen
original sink line and all gold trace files together in one SARIF thread flow.
A safe case requires zero findings after those same coverage checks.

The gold names and expected outcomes are:

- `cpp_to_c_T`: finding; `cpp_to_c_F`: clean. C++ getenv to C system.
- `c_to_cpp_T`: finding; `c_to_cpp_F`: clean. C getenv to C++ extern C system.
- `cross_language_return_T`: finding; `cross_language_return_F`: clean. Return from a C source into a C++ sink.
- `pointer_writeback_T`: finding; `pointer_writeback_F`: clean. C writes through a pointer consumed by C++.
- `c_registers_cpp_callback_T`: finding; `c_registers_cpp_callback_F`: clean. C registers and dispatches a C++ callback.
- `namespace_extern_c_T`: finding; `namespace_extern_c_F`: clean. Namespace-scoped C++ definition has C linkage.
- `inherited_extern_c_T`: finding; `inherited_extern_c_F`: clean. Later definition inherits the earlier extern C prototype.
- `cpp_same_name_distinct_from_c_abi_T`: finding; `cpp_same_name_distinct_from_c_abi_F`: clean. Ordinary C++ and C ABI functions with the same source spelling coexist in one linked executable.
- `separate_domains_same_names_T`: finding; `separate_domains_same_names_F`: clean. Two complete programs share names. In the safe case the tainted caller's only implementation is safe; the dangerous implementation belongs to the other domain, whose caller uses a constant.
- `header_macro_c_and_cpp_T`: finding; `header_macro_c_and_cpp_F`: clean. A shared .h is included under C/C++ and different macros defined before the include; the C context remains safe.
- `static_and_anonymous_per_tu_T`: finding; `static_and_anonymous_per_tu_F`: clean. Static functions and anonymous-namespace storage remain local to their C++ TU.
- `external_inline_shared_static_T`: finding; `external_inline_shared_static_F`: clean. Two C++ TUs share the local static of one external inline function. The positive trace includes the writing TU as well as the source and sink TUs.
- `internal_staticinline_separation_T`: finding; `internal_staticinline_separation_F`: clean. Static inline local storage is shared within one TU and distinct across TUs.
- `missing_generated_header`: nonzero exit and a manifest covering every selected unit, including a failed sink TU and a diagnostic naming `generated.h`. The frozen header is present for compile/link proof; only its temporary staged copy is removed before scanning.

Only ordinary functions, pointers, constant initialization, namespaces, linkage,
and inline/static storage are used. Each program includes the real `<stdlib.h>`;
no handwritten substitute for libc declarations hides system-header metadata.
The existing raw `.h` C/CPP selection regression is unchanged.

Initial verification on 2026-11-09 used Apple Clang 21.0.0 with C17/C++17.
All 27 fixtures produced 64 object files and 29 linked programs, with every
compiler/linker command exiting 0. No fixture program was executed.
Frozen gold SHA256:
`ae7a9b326068054040a678e524f6009b2e10daf225377d70d51004fd55183e3d`.

The first launch used an incorrect Mocha filename and was retained separately as
`../verification/mixed/acceptance-launch-error.log` relative to `engine`. The
corrected executable run is preserved as
`../verification/mixed/acceptance-red.log`. The concurrent runner became available
during fixture setup, so this run reached analysis instead of the originally
anticipated unsupported-command error. It exited 2: 25 tests passed and 2 failed:

- `external_inline_shared_static_T`: finding exists, but its trace omits `store.cpp`.
- `static_and_anonymous_per_tu_F`: false positive from tainted state crossing TUs.

No labels, trace expectations, or fixture bytes were changed after that run.
The test retains its temporary evidence directory (printed in the log), including
`gold-frozen.json`, all compile/link commands in `build-proof.json`, compilation
databases, profiles, linked programs, CLI logs, manifests, and SARIF. Test-only
TypeScript checking passed. Production fixes and integration belong to the main
implementer; this handoff does not claim the mixed implementation passes.
