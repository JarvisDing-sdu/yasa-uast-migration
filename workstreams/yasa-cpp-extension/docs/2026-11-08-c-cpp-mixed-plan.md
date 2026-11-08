# C/C++ 混合项目统一扫描 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变旧 C/CPP 模式行为的前提下，新增按真实编译上下文解析头文件、连接跨语言调用和污点、输出可审计覆盖情况的混合项目扫描。

**Architecture:** 新增显式 `c-cpp` 驱动，读取 compilation database 和构建选择清单；按 TU 调用编译器只预处理，再使用现有 C/CPP 前端。每个链接范围独立创建分析状态，通过具备语言链接信息的符号索引连接函数；最后合并展示报告，不合并互斥状态。

**Tech Stack:** TypeScript / Node.js、现有 tree-sitter-c 与 tree-sitter-cpp 0.23.4 / web-tree-sitter 0.26.x、实际 Clang/GCC 预处理驱动、Mocha/tsx、Python 3 验收脚本。

**Spec:** `workstreams/yasa-cpp-extension/docs/2026-11-08-c-cpp-mixed-design.md`。该文档与本计划是待确认草案；本次只生成文档，不执行下列步骤。

## Global Constraints

- 旧 `--language c`、`--language cpp` 保持兼容；新增 `--language c-cpp`，不把旧模式默认改成混合模式。
- 现有 C、C++ parser 继续保留，公共代码继续复用；不整体替换为 Clang AST，不增加完整 C++20/Windows 工具链承诺。
- 初版正式混合扫描要求编译数据库和构建选择清单齐全。目标归属、编译器或必要参数不确定时，返回明确诊断，不静默猜测。
- 不做测试特判、不改标签；原基线、原 M1 结果和原始证据均保留，新结果另存。
- 每个实现任务先写失败测试、确认失败再修复。涉及 Engine 或 parser-C 的任务必须跑完整 C 回归；涉及 C++ 路径同时重跑 CPP 测试。
- C 对照：原 parser-C 72、Engine C 112 测试全部通过；sast-c TP110/FN0/TN54/FP0 且逐例相同；2,451 个 UAST 哈希相同；四组 Juliet C 逐例相同；curl 严格 TP7453/FP0/FN57、full_ast 6877、人工回调 25/25，三个评分对象完全相同。
- CPP 对照：原 parser-CPP 18、Engine CPP 40 测试保留；计分器 13 项与自测通过；与 `results/m1-review-fixes/juliet` 的 8 份完整 JSON 比较。语义改善造成的 FN→TP 必须单独审计，不能改基线掩盖变化。
- 提交身份 `sijie52 <sijie5452@gmail.com>`；不增加 AI 共同作者署名。中文报备；本地提交可做，推送、合并、发布另行确认；不直接删除已有文件。

## Review Focus

1. `.h` 的显式语言选择、`-x` 覆盖后缀、带空格/引号的路径、同一文件多条命令 → Task 1/2 的命名测试。
2. include 前的宏、同一头的 C/CPP/多宏上下文、生成头缺失及依赖变更 → Task 3/4，不按文件名复用缓存。
3. 不同程序/互斥配置、同路径多个 TU、static/匿名/inline 定义误合并 → Task 2/5 的隔离与冲突负例。
4. C ABI、命名空间内 extern C、仅名字相同的 CPP 函数、回调与指针写回 → Task 4/5/6 的编译链接和污点测试。
5. worker 上下文串用、读取数伪装解析数、失败扫描变零告警、宏展开行列定位和重复告警 → Task 3/4/6/7 的完整性测试。

## 文件职责与仓库边界

下列路径以集成仓库为根；`Create` 均为拟新增文件，不表示已经实现。沿用 `workstreams/yasa-cpp-extension` 保存计划与验收资料，Engine/UAST 改动分别提交在子模块，集成仓库最后固定指针。

- `engine/src/engine/parser/c-family/`：编译上下文、命令读取、编译器预处理、位置映射、TU 解析与 manifest；不放污点规则。
- `engine/src/engine/analyzer/c-family/common/`：符号身份、模块隔离、单链接范围分析。
- `engine/src/interface/c-family-runner.ts`：新模式的多范围调度；旧模式继续使用原启动路径。
- `engine/src/checker/taint/c-family/` 与新的规则包：只注册一次混合 checker，沿用已有 source/sink 的语义。
- `uast/parser-C/src/parser.ts`、`uast/parser-CPP/src/parser.ts`：增加显式预处理输入 API；旧 parse 路径不变。
- `engine/test/c-family/` 与工作流 `fixtures/mixed/`：独立程序测试及冻结 gold；不混进旧 C 快照语料目录。
- `workstreams/yasa-cpp-extension/scripts/`、`results/mixed/`：验收脚本与版本化 summary；原始产物放新的 outputs 子目录。

## 跨任务数据契约

在 `engine/src/engine/parser/c-family/build-context.ts` 定义并导出；类型可扩充诊断字段，但后续任务不自行重命名核心字段。

```typescript
type Language = 'c' | 'cpp'
interface Diagnostic { code: string; stage: string; message: string; unitId?: string }
interface CompileEntry {
  entryId: string; directory: string; sourceFile: string; argv: string[]
}
interface BuildSelection {
  version: 1; profileId: string
  units: { entryId: string; domainId: string }[]
  environment?: Record<string, string>
}
interface BuildContext extends CompileEntry {
  unitId: string; profileId: string; domainId: string; language: Language
  standard: string | null; environment: Record<string, string>
}
interface Dependency { file: string; sha256: string; system: boolean }
interface Origin { file: string; line: number; column?: number; system: boolean }
interface MapSegment { generatedStartLine: number; generatedEndLine: number; origin: Origin }
interface PreparedUnit {
  context: BuildContext; text: string; sourceMap: MapSegment[]
  dependencies: Dependency[]; artifactHash: string; compilerId: string
  diagnostics: Diagnostic[]; status: 'prepared' | 'failed'
}
interface ParsedUnit {
  prepared: PreparedUnit; ast: unknown | null; diagnostics: Diagnostic[]
  status: 'parsed' | 'partial' | 'failed'
}
```

ID 规则：`entryId = SHA256(JSON.stringify([resolvedDirectory,resolvedSourceFile,argv]))`；路径相对编译记录的 directory 解析，不擅自 realpath 改变 include 语境。argv 顺序保留。`unitId = SHA256(JSON.stringify([profileId,domainId,entryId]))`。同条记录可在不同 domain 被选入；同一 domain 的重复 entryId 去重；有冲突定义时不得按先后顺序选一个。

`artifactHash` 覆盖 TU 实际预处理文本、编译上下文、实际驱动/版本、相关环境、传递依赖内容及前端版本；跨运行复用前要重新验证依赖，新增、删除、生成头变动也使缓存失效。不在验证依赖前直接命中旧 AST。

## Task 1：M1 收口与单文件语言选择

**Files:** Modify `engine/src/interface/starter.ts`；Create `engine/test/c-family/test-language-selection.ts`；更新工作流的复审与基线清单，保留原报告。

**Interfaces:** 保持 CLI 既有语言/分析器选项；单文件后缀推断只在没有显式语言、分析器或配置语言时补默认值，不覆盖用户选择。不改变现有显式 analyzer 的优先级规则。

- [ ] Step 1：对 M1 修复提交作独立只读复审，记录未解决项；若存在影响后续复用的阻断项，先另作修复，不把“已本地测试”写成“已独立审过”。
- [ ] Step 2：新增 `explicit_cpp_header_wins_over_suffix`、`explicit_c_header_stays_c`、`analyzer_language_is_preserved`、`header_without_language_keeps_legacy_c_default`；用扫描摘要/AST 的 language 和 namespace 保留情况断言，不只断言无异常。
- [ ] Step 3：运行 `cd engine && npx mocha --require tsx/cjs test/c-family/test-language-selection.ts`，确认 CPP .h 的回归在原实现失败。
- [ ] Step 4：最小修改单文件入口的默认语言选择；原项目模式不变。
- [ ] Step 5：运行上述测试、原 test-c/test-cpp、tsc、完整 C 回归并比较。期望原测试全通过，非测试 C 结果无差异。
- [ ] Step 6：Engine 单独提交 `fix(cli): preserve explicit language for single headers`；冻结本轮输入/版本/旧结果哈希。

## Task 2：编译记录与构建范围

**Files:** Create `engine/src/engine/parser/c-family/build-context.ts`、`engine/src/engine/parser/c-family/compilation-database.ts`、`engine/src/engine/parser/c-family/build-selection.ts`；Create `engine/test/c-family/test-build-context.ts`、`test/c-family/fixtures/configs/`。

**Interfaces:**
- `readCompilationDatabase(file: string): Promise<CompileEntry[]>`。
- `selectBuildContexts(entries: CompileEntry[], selection: BuildSelection): BuildContext[]`。
- `parsePosixCommand(command: string): string[]`：仅词法拆分引号，不展开环境变量、不执行 shell；优先 arguments。
- `resolveLanguage(entry: CompileEntry): Language`：尊重有效 `-x`，其次驱动与源后缀；无法确定时报诊断。

- [ ] Step 1：固定测试：`arguments_preserve_D_U_order`、`quoted_command_and_spaces`、`x_cpp_overrides_dot_c`、`relative_directory_uses_database_parent`、`same_source_multiple_entries_remain_distinct`、`two_domains_do_not_merge`、`unknown_entry_is_rejected`。
- [ ] Step 2：运行新测试确认缺失接口导致失败；测试不得执行编译命令。
- [ ] Step 3：实现 schema、ID、路径与参数读取。清单优先选择，不从 compilation database 猜链接目标；缺清单/冲突条目返回诊断。响应文件、包装器、多个源输入、未支持 shell 结构和必要参数缺失都明确拒绝，不能吞掉。
- [ ] Step 4：相关环境只采用 profile 声明及本次实际编译环境，并记录来源；不能声称重建了未记录的历史构建环境。宏和搜索路径顺序始终保留在 argv。
- [ ] Step 5：新测试通过，原测试/tsc/完整 C 对照通过；提交 `feat(c-family): model compile contexts and link domains`。

## Task 3：编译器辅助预处理与原位置

**Files:** Create `engine/src/engine/parser/c-family/compiler-preprocess.ts`、`engine/src/engine/parser/c-family/source-map.ts`；Create `engine/test/c-family/test-preprocess.ts` 与独立小程序 fixtures。

**Interfaces:**
- `preprocessUnit(context: BuildContext, outDir: string): Promise<PreparedUnit>`。
- `decodeLineMarkers(text: string, cwd: string): { text: string; sourceMap: MapSegment[] }`。
- `mapOrigin(map: MapSegment[], generatedLine: number, generatedColumn: number): Origin | null`。

- [ ] Step 1：写真实编译器测试：`header_follows_c_or_cpp`、`define_before_include_changes_header_body`、`two_D_values_do_not_share_header_ast`、`missing_generated_header_is_failed`、`dependency_change_invalidates_artifact`、`header_sink_maps_to_original_line`、`macro_sink_without_column_does_not_invent_column`、`line_directive_keeps_logical_and_physical_provenance`。
- [ ] Step 2：运行测试观察失败。测试前检查 Clang/GCC 可用；正式验收缺编译器判未完成，不能以 skip 算通过。
- [ ] Step 3：通过 execFile/spawn 的 argv 与 cwd 调实际已选择的直接驱动，仅 -E；移除编译、输出及依赖生成动作。保留影响预处理的参数和顺序。未支持必要选项、驱动报错或超时返回 failed，原始 argv/日志保留。
- [ ] Step 4：保留 GCC/Clang 行标记及依赖，生成可定位的 TU 文本。原文件与行号必须准确；行标记不能提供可靠原列时，Origin.column 留空，禁止填预处理列伪装原列。宏告警主位置取展开调用点，能获得定义点时另附，不承诺完整嵌套 token 来源；`#line` 的逻辑位置与真实依赖的物理文件/内容哈希分开存，不能把伪逻辑文件当磁盘输入；多处同原行调用用 unitId+生成区间区分。
- [ ] Step 5：默认每 TU 预处理 120 秒，超时记录失败；正式预算改变要在新 profile 和报告中显式记录，不偷偷重试成另一配置。
- [ ] Step 6：通过新测试及完整旧回归后，提交 `feat(c-family): preprocess translation units with source provenance`。

## Task 4：预处理 TU 到 UAST，含 worker 与语言链接信息

**Files:** Modify `uast/parser-C/src/parser.ts`、`uast/parser-C/src/index.ts`；Modify `uast/parser-CPP/src/parser.ts`、`uast/parser-CPP/src/index.ts`、`uast/parser-CPP/src/handlers/index.ts`；Create `uast/parser-CPP/src/handlers/linkage.ts`；Create `engine/src/engine/parser/c-family/c-family-ast-builder.ts`；Modify `engine/src/engine/parser/parser.ts`、`engine/src/engine/parser/parser-worker.ts`、`engine/src/engine/parser/parser-core.ts`；Create `engine/test/c-family/test-tu-parser.ts`；Modify `uast/parser-C/tests/index.ts`、`uast/parser-CPP/tests/index.ts`。

**Interfaces:**
- 两个 Parser 类新增 `parsePreprocessed(content: string, opts: Record<string, unknown>): UAST.Node`；参数含 sourcefile、languageVersion。CPP 调用共享 `parseWithParser` 的扩展，不能重新覆盖实际编译宏；旧 parse 不变。
- `parsePreparedUnit(prepared: PreparedUnit): Promise<ParsedUnit>`。
- `parseContextTasks(units: PreparedUnit[], workers: number): Promise<ParsedUnit[]>` 在 Engine parser 模块导出，worker 收到完整不可变上下文和位置映射。
- 编译单元 `_meta.cFamily = {unitId,profileId,domainId,sourceFile,artifactHash}`；函数/原型/外部变量先输出 `_meta.lexicalLanguageLinkage = 'C' | 'C++'` 及 `_meta.languageLinkageExplicit`，表示词法提示；新增 `_meta.storageLinkage` 区分 external/internal/none，并沿用 static/anonymous 等依据。Task 5 结合先前声明计算最终 `_meta.languageLinkage`，入索引前该字段必须已经是有效语言链接，不能直接用词法默认值创建键。节点保留原位置及 `_meta.generatedRange`；列未知另标 `_meta.originalColumnKnown=false`。

- [ ] Step 1：写失败测试：`header_function_body_enters_tu`、`no_second_macro_expansion`、`extern_c_block_and_single_declaration_are_retained`、`namespace_extern_c_has_C_linkage`、`same_file_two_contexts_have_distinct_node_ids`、`worker_and_main_results_equal`、`worker_reuse_does_not_keep_previous_macros`。
- [ ] Step 2：解析预处理输入时跳过旧宏分支覆盖及宏展开，复用常规访问器；CPP linkage handler 按词法范围向下传递，不能只在 wrapper 上留标记；C 默认语言链接 C，CPP 默认 C++。
- [ ] Step 3：位置映射与节点 ID 分离：节点/模块身份含 unitId，展示位置指向原文件。物理源码缓存可共享原始文件内容，TU/AST/语义缓存按上下文隔离，不能以同路径覆盖。
- [ ] Step 4：系统头声明保留；系统实现由新模式的库策略处理。新增 `project_function_in_angled_header_is_not_dropped`、`system_library_declaration_keeps_source_sink_models`，不按尖括号或路径名猜是否应分析。未建模声明/类型明确进入诊断。
- [ ] Step 5：worker 新任务分支不读写全局 Config.cPreprocessor；主线程/OOM fallback 使用同一不可变输入。旧 worker 分支保持行为。
- [ ] Step 6：运行两个 parser 构建/测试、新 worker/TU 测试、原 Engine 测试、tsc、完整 C 比较。提交 UAST 与 Engine 各自变更；阶段 B 的技术可行性检查不过则停止后续集成。

## Task 5：统一符号、模块身份与调用图

**Files:** Create `engine/src/engine/analyzer/c-family/common/symbol-index.ts`、`engine/src/engine/analyzer/c-family/common/static-storage.ts`、`engine/src/engine/analyzer/c-family/common/c-family-analyzer.ts`；Modify `engine/src/engine/analyzer/c/common/c-analyzer.ts`、`engine/src/engine/analyzer/cpp/common/cpp-analyzer.ts`、`engine/src/checker/callgraph/callgraph-checker.ts`；Create `engine/test/c-family/test-symbols.ts`、`engine/test/c-family/test-callgraph.ts`。

**Interfaces:**
- `CFamilyAnalyzer extends CppAnalyzer`，每个 domain 独立实例；`loadUnits(units: ParsedUnit[]): Promise<void>` 只接收该 domain 的单元。
- `resolveEffectiveLinkage(units: ParsedUnit[]): void`：按 TU 的可见声明及顺序，把词法提示解析为有效 `_meta.languageLinkage`；头文件 extern C 原型后的未重复 wrapper 定义继承 C 链接。
- `CFamilySymbolIndex.register(definition: unknown, value: unknown, context: BuildContext): void`；`resolve(reference: unknown, context: BuildContext, lexicalScope: unknown): { scope: unknown; name: string } | null`。
- 索引键包括 domain、外部语言链接、规范名及支持的签名；内部定义另含 unitId。CPP 命名空间内 extern C 保留 CPP 词法别名，但连接 C ABI 的同一绑定。重载选择未实现时返回未建模诊断，不按裸名混接。

- [ ] Step 1：先编译并链接冻结 fixtures：`cpp_calls_c_extern_c`、`c_calls_cpp_extern_c`、`cpp_same_name_without_extern_c_stays_separate`、`namespace_extern_c_resolves_c_definition`、`extern_c_declaration_governs_later_definition`、`cpp_const_internal_c_const_external`、`header_static_per_tu`、`anonymous_per_tu`、`same_source_multiple_domains`、`conflicting_external_definitions_reported`、`external_inline_local_static_shared_across_tus`、`static_inline_local_static_stays_per_tu`；预期边与禁止边都固定。
- [ ] Step 2：单独验证 index 注册/查找，再运行 CLI/分析器调用图断言；当前实现应不能通过跨语言与多上下文场景。
- [ ] Step 3：新增受保护的模块身份/导出绑定扩展点，旧实现仍使用原逻辑。当前 CAnalyzer 的 moduleScopes/types/callbacks 私有，不能从子类硬取；提供只读 protected 访问器或受控注册 hook，单独提交并验证无行为变化。CppAnalyzer 必须让子类替换读写绑定与函数/变量登记，不能先向裸名 topScope 泄漏再补一个索引。
- [ ] Step 4：新模式模块键使用 unitId；类型/回调候选也携带 TU 和 domain，物理文件路径只供源码定位。内部/外部链接遵循具体语言；例如 CPP 命名空间级的顶层 const 对象默认内部链接，与 C 不同，不能把“类型里出现 const”粗暴等同顶层 const。注册前先调用 resolveEffectiveLinkage，在 TU 内收集并匹配声明/定义，传播有效语言链接，继承早先 extern C 原型；显式冲突诊断，不能让默认 CPP 标记覆盖既有 C 链接。同一外部 inline 定义的重复实例仅在来源、签名和预处理体等价时合并；静态定义始终隔离，冲突定义诊断不静默覆盖。为新模式增加普通外部 inline 的局部 static 存储：以 canonical function key+变量声明身份为键，在同一执行路径第一次调用时初始化、后续复用；内部函数另含 unitId。不改变旧 C 局部变量的执行方式，不宣称支持全部动态初始化/线程局部存储。
- [ ] Step 5：调用图边携带 profile/domain/unit、链接证据和原位置；列未知仍保持调用点实例唯一。C/CPP 旧图格式及评分保持不变。
- [ ] Step 6：新正反测试、旧回调/CPP 测试、完整 C 回归通过后提交；只连通图尚不计作漏洞链验收通过。

## Task 6：污点贯通、统一入口与可信报告

**Files:** Create `engine/src/interface/c-family-runner.ts`、`engine/src/engine/parser/c-family/analysis-manifest.ts`、`engine/src/checker/taint/c-family/c-family-default-taint-checker.ts`；Modify `engine/src/interface/starter.ts`、`engine/src/config.ts`、`engine/src/checker/taint/cpp/cpp-default-taint-checker.ts`、`engine/src/checker/common/output/taint-output-strategy.ts`、`engine/resource/checker/checker-config.json`、`engine/resource/checker/checker-pack-config.json`、`engine/package.json`；Create `engine/resource/example-rule-config/rule_config_c_family.json`、`engine/test/c-family/test-taint.ts`、`engine/test/c-family/test-report.ts`。

**Interfaces:**
- `runCfamily(request: {sourcePath:string; compileCommands:string; buildProfile:string; reportDir:string; workers:number}): Promise<{status:'complete'|'partial'|'failed'; manifestPath:string}>`。
- 新模式命令：`--language c-cpp --compileCommands FILE --buildProfile FILE`；一份 profile 可声明多个 domain，顺序分析并汇总展示。新模式使用显式参数，不读取旧全局宏默认值；混用旧 `--cDefine/--cUndefine/--cIncludeDir/--cTarget` 显式覆盖选项时报配置冲突，避免假称重现构建。
- 新 checker `taint_flow_c_cpp_input`、包 `taint-flow-c-family-default`；CPP checker 构造函数可接受可选 checkerId，默认值仍为原 CPP ID。
- `analysis-manifest.json` 每 unit 保留终态：`analyzed/partial/preprocess_failed/parse_failed/analysis_failed/timed_out/unsupported`，并记录声明、未解析调用、未建模类别、耗时、配置与产物哈希；另列未入选源码及理由。

- [ ] Step 1：冻结并真实链接以下用例及其安全对照：C++ source→C sink、C source→CPP extern C sink、跨语言返回值、指针写回、C 注册 CPP 回调。source/sink 选择沿用规则，例如 getenv/system；安全对照使用常量或已有对应安全模型，不改标签。
- [ ] Step 2：运行新测试确认失败；既断言漏洞结果，也断言 trace 中真实跨语言边和函数实例，防止靠两端各自扫到无关告警蒙混。
- [ ] Step 3：把同一 domain 的 C/CPP 函数放在同一分析状态中，调用与参数、返回值、指针绑定直接进入已有符号解释器。不同 domain 用全新分析器及 entrypoint 状态；不合并两次独立扫描的 SARIF 来模拟贯通。
- [ ] Step 4：仅新模式注册一份混合 checker，源/sink 模型沿用既有内容。系统声明按库策略建模，用户命名空间同名函数沿自身实现分析；新增 `custom_system_getenv_atoi_are_not_libc` 对照。
- [ ] Step 5：新增 `failed_unit_cannot_be_zero_findings_success`、`read_file_is_not_parsed_unit`、`all_selected_units_have_terminal_state`、`same_header_finding_keeps_all_contexts`、`different_domain_findings_do_not_dedupe_together`、`unknown_column_is_omitted_in_sarif`。SARIF 重复汇总的键含规则、原位置、语义路径及 domain；同原行不同调用不误合。
- [ ] Step 6：starter 在旧单语言初始化前分流到新 runner；不把项目语言 c-cpp 直接传给只支持具体语法的 parser。新模式 partial/failed 非零退出，仍保存部分报告并标 coverage incomplete；零发现且 complete 才是有效完成扫描，不能据此声称代码安全。
- [ ] Step 7：package.json 新增 `test-c-family`，列出上述全部命名测试文件。运行新全套及旧全套、tsc、完整 C 比较、8 组 CPP Juliet；提交 Engine 集成，不推送。

## Task 7：受控验收、真实项目审计与结果保留

**Files:** Create `workstreams/yasa-cpp-extension/fixtures/mixed/`、`workstreams/yasa-cpp-extension/scripts/mixed_regression.py`、`workstreams/yasa-cpp-extension/scripts/tests/test_mixed_score.py`、`workstreams/yasa-cpp-extension/results/mixed/`；Modify `workstreams/yasa-cpp-extension/README.md`，另增本阶段账本和复审请求，不覆盖 M0/M1 原文件。

**Interfaces:**
- `python3 scripts/mixed_regression.py run --engine PATH --manifest FILE --out NEW_DIR`：manifest 固定源码/编译器/编译数据库/profile/规则/gold 的哈希、案例和项目清单，输出原始日志与单元终态。
- `... score --run NEW_DIR --json NEW_RESULT`：先校验运行完整性、预期单元、哈希与告警归属，再计分；非零批次、缺单元或 unmapped 不产生正式“通过”结论。
- `... compare-legacy --new DIR --baseline results/m1-review-fixes`：调用已有 C compare，检查 CPP 单测与八份结果；不重写已有 C 计分器。

- [ ] Step 1：把 Task 1–6 的 fixtures、危险/安全标签、预期调用边和定位结果冻结；首次运行新实现前确定清单。系统测试样例不进入旧 corpus，既有 M1 混合文件选择测试保留原语义。
- [ ] Step 2：先验证评分器正负例，包括零发现、运行中断、源/配置哈希变化、缺报告/缺 TU、未知告警位置、仅有效子集、归档后重计分。gold 每个实例固定 case/profile/domain/根 TU/调用点身份，在展示去重前匹配；增加 `one_header_hit_cannot_cover_another_context_miss`。运行完整性失败则拒绝发布正式通过分数，原正负例分母和失败实例数量仍完整列出；部分统计同时给出 TP/全部冻结正例。完整运行但因未建模漏报的实例计 FN。
- [ ] Step 3：从本地 aria2/cppcheck 指定提交准备独立构建目录和真实编译数据库；记录目标的实际 C/CPP 成员。aria2 优先启用 wslay 的目标；若该配置不可构建，记录失败再提交替代候选理由，不能拿仓库后缀数量冒充混合构建证明。
- [ ] Step 4：调用点审计按设计中的 ≤30 全量、>30 固定种子抽取至少 30 执行；直接调用对照编译器/Clang 信息，间接调用由人工建立 gold。对新告警标注成立/误报/证据不足，保留证据和未审计数量；同时报告保守确认比例 TP/全部已审告警，不能只在证据充分的子集里计算。
- [ ] Step 5：新模式运行前冻结可构建的已知漏洞修复前/后样本清单，逐例保留根因与预期；无适当样本或未检出则报告限制，不把注入测试写成真实漏洞命中。
- [ ] Step 6：报告分开给出 TP/FP/FN、未完成项和覆盖。若运行完整性失败，整体验收失败，只能给明确标注的部分统计；没有完备真实项目 gold 时召回率记 N/A。计时与峰值内存列出，预算/参数变化可追踪。
- [ ] Step 7：在最终代码上运行完整 C、CPP、新混合回归，核对旧文件哈希；将原始输入副本、预处理产物、配置、UAST/位置映射、调用图/SARIF、全部日志保存到新的 outputs 子目录，生成哈希清单并验证归档重计分。
- [ ] Step 8：提交结果摘要与子模块指针，独立复审符号边界、污点链和失败统计。交付阶段 B/C/D 各自通过与否的结论，等待用户决定集成；不自动推送/合并。

## 执行约定与后续范围

推荐同一主执行者按 Task 1→7 串行实现，关键接口与最终结果独立审阅；这些任务共享 TU、符号和报告契约，不适合同时各写一套接口。当前用户只要求计划书，未开始执行。实施时先建立隔离分支/工作区，记录旧三个 HEAD，再按任务提交。

类/成员/虚函数、引用别名、动态全局初始化 source、STL/字符串/文件流仍按后续 M2/M3 各自写计划与验收。发现真实目标依赖这些能力时，在本轮覆盖报告中如实显示，不把混合入口上线等同于完整支持 C++。

## 计划自检

交付前检查：Goal 和各阶段均能映射到任务；Review Focus 五类均有命名测试；数据契约、CLI、checker ID 和 profile 字段一致；新增路径标明 Create，现有路径核对存在；旧 C/CPP 验收与 mixed 验收明确分开；所有“通过”均指未来执行的预期，未把这次写文档当成完成了实现。
