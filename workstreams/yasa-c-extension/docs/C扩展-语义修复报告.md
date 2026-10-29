# C 扩展：语义修复报告（独立测试复核后）

独立测试（52 个语义边界用例 + 8 个真实 API 用例 + 运行时 oracle）指出了 C 支持在真实 C 语义下的漏报和误报。本轮先复现、再把失败固定为回归用例、最后按根因修改实现。没有删除或跳过用例，没有放宽断言，没有关闭 checker、扩大 sanitizer 或忽略文件，没有修改测试标签，也没有针对文件名、函数名或靶场特征做特判。

被测版本（修复前）：integration `b8db890`、engine `3fc472c`、uast `0561b39`。

## 1. 复核结论

修复前在本机复现，结果与独立测试一致：52 个用例 TP 23 / FN 9 / TN 8 / FP 12，8 个真实 API 用例 FN 5 / FP 3；运行时 oracle（clang 编译运行）14/14 期望成立。独立测试指出的问题全部属实，逐项按根因修复。

## 2. 根因与修改

| # | 问题 | 根因 | 修改（文件） |
| --- | --- | --- | --- |
| 1 | struct 按值复制/按值传参后字段互相影响（`struct_copy_value` 漏报、`struct_copy_no_alias`/`struct_by_value_parameter` 误报） | 引擎对象按引用共享，`b = a` 让 b、a 成为同一对象；分析器不知道表达式的声明类型 | 新增 `c-types.ts`：按词法作用域给变量引用标注声明类型，登记 struct 字段类型与 typedef。`c-analyzer.ts`：`struct S b = a`、`b = a`、按值形参（`onParamsBound`）、`*ps = b` 时按类型复制——字段独立，嵌套 struct/数组成员递归复制，指针成员只复制指针值（仍共享被指对象），不做整体深拷贝 |
| 2 | 多级指针写回失效（`**r = v` 漏报） | `&x` 返回 x 的值本身，用值对象做“地址→位置”表的键：`&p` 和 `&q` 指向同一个值对象，后一次覆盖前一次 | `c-analyzer.ts`：标量/指针变量的 `&x` 产生独立的地址值并记录其位置；`*e = v`/`*e` 用 e 的当前值查表，逐级定位位置；去掉“写入后让指针继续指向新值”的近似。覆盖多级解引用、别名读取、指针重绑定（`*r = &o`）、`char ***` 输出参数、`&s.a` |
| 3 | 宏顺序、`#undef`、头文件宏、条件环境（`macro_redefine_*`、`macro_defined_after_use`、`header_macro`） | `collectMacros` 扫描整个文件，每个名字只保留一个定义（且优先非 Windows 分支），忽略位置、`#undef` 和 `#include` | parser-C `macros.ts` 重写为 `MacroEnvironment`：像预处理器一样按行顺序扫描本文件和头文件，宏按位置生效，`#if` 在编译配置下三值求值，配置排除的行在解析前替换为空格；未决定的条件保留所有可能分支，使用处有多个可能定义时展开为未知条件的选择。编译配置显式输入：Engine `--cDefine`/`--cUndefine`/`--cTarget`（默认 linux）/`--cUnknownMacros cover\|undefined`/`--cIncludeDir`（`config.ts`、`starter.ts`、`c-ast-builder.ts`） |
| 4 | goto 剪枝错误（`goto_skips_intermediate_label` 误报、`goto_bypasses_sanitizing_assignment` 漏报）、嵌套块 return、短路、`if (1-1)` | 只在同一块内剪掉 return/goto 之后的语句，遇到任意标签就恢复；return 不跨块传播；常量条件只认字面量；`&&`/`||` 右侧总被求值 | `c-analyzer.ts`：每次函数调用一个控制流状态（不可达标记 + 待跳转标签 + 标签处的变量快照）。只在匹配的目标标签恢复，可跳出嵌套块；条件 goto 的路径在目标标签合并；if 两分支都突然完成时之后不可达；循环中 break/continue/return；switch 中 break。新增 `c-const-eval.ts` 折叠 C 整数常量表达式，`&&`/`||` 短路、三目常量条件只求值被选分支；单分支 `if (c) { ...; return; }` 中分支的写入不流到 if 之后（条件本身的写入，如 `if (sscanf(..., &id) != 1) return;`，保留） |
| 5 | 编译单元链接（`header_static_name_collision` 漏报、条件重复定义取第一个） | 头文件 `static inline` 函数注册到全局并取第一个；同名函数在 `#if` 两个分支中定义时取第一个 | parser 记录 `CompileUnit._meta.includes` 并给未决定分支中的定义加 `_meta.conditional`；`c-analyzer.ts`：头文件 static 函数放进包含它的每个 .c 的模块 scope；条件分支中的同名定义保存为并集，调用时每个都执行；配置排除的分支（如 Linux 下的 `_WIN32`）在解析前已去掉 |
| 6 | libc 模型（覆盖不清除、长度 0、snprintf 多余实参、atoi 屏障丢失长度风险） | 输出参数只在源实参带污点时重绑定，干净写入不清除；未看长度与格式串；atoi 返回干净值 | `c-builtins.ts` 重写：完整覆盖（strcpy、sprintf、长度覆盖整个 dst 的 memcpy/memset/strncpy）后 dst 只带写入内容的污点；部分写入保留原内容；长度常量 0 不写入；格式串逐个对应实参（`%%`、`*`、`%n`、位置）；`sscanf` 按转换写入。数值污点：`atoi`/`strtol`/`strlen` 结果与 `%d` 等写入的数字文本带 `cNumericTaint`，命令/路径/SQL 等注入类 sink 忽略，长度类与格式串类 sink 仍报告（`c-default-taint-checker.ts`） |

## 3. 结果（修复前 → 修复后）

| # | 验收项 | 命令 | 修复前 | 修复后 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| 1 | parser-C 单测与构建 | `cd uast/parser-C && npm test && npm run build` | 50/50 | 56/56（新增 6 个预处理语义用例） | 0 / 0 |
| 2 | Engine C 回归与类型检查 | `cd engine && npx tsc --noEmit -p . && npm run test-c` | test-c 3/3 | 82/82（原 3 个 + 语义回归 79 个：78 个用例 + 正反例数量检查） | 0 / 0 |
| 3 | 原 sast-c 82 个用例 | 见 §5 | TP 65 FN 0 TN 17 FP 0 | TP 65 FN 0 TN 17 FP 0 | 0 |
| 4 | 独立测试 52 个用例 | `YASA_REPO=<repo> python3 -I run_suite.py --jobs 4` | TP 23 FN 9 TN 8 FP 12 | **TP 32 FN 0 TN 20 FP 0** | 0 |
| 5 | 8 个真实 API 用例（默认规则） | `run_suite.py --default-rules --only real_*` | TP 0 FN 5 TN 0 FP 3 | **TP 5 FN 0 TN 3 FP 0** | 0 |
| 6 | 新增回归变体（78 个，42 T / 36 F） | 见 §5 | TP 18 FN 21 TN 12 FP 22（最初 73 个的修复前基线） | TP 42 FN 0 TN 36 FP 0 | 0 |
| 7 | CASTLE 污点类 40 个文件 | `castle_c.py ... --rules rule_config_c.json` | TP 24 FN 0 TN 6 FP 10 | TP 24 FN 0 TN 6 FP 10（250 个文件逐个结果与修复前相同） | 0 |
| 8 | 其它语言回归 | 见下 | — | 公共 Analyzer（`engine/src/engine/analyzer/common`）未修改，见下 | — |

- 运行时 oracle：独立测试的 `runtime_oracle.py` 14/14 期望成立；新增用例的 clang oracle（`scripts/c_semantics_oracle.py`）76/76 标签与实际运行一致，2 个 sink 为长度/格式串的数值用例无法按输出内容判定（按 C 语义标注，见脚本）。
- 其它语言：本轮只改了 C 专用文件和两个公共文件的追加部分（`config.ts` 新增 `cPreprocessor` 默认值、`starter.ts` 新增 `--c*` 命令行选项），公共 Analyzer 与公共 checker 未改。`test-callargs` 86/86 与修复前相同；`test-php-checker` 修复前后都是 7 通过 / 4 失败（`CheckerManager_ctor` 环境问题，修复前同样失败）；Python/Go/Java/JS 的 benchmark 测试依赖外部靶场仓库，本环境没有，**未运行**。
- 大项目解析（`c_corpus_parse.ts`，Redis/curl/SQLite）：0 崩溃，解析耗时与修复前相当（修复前 → 修复后：Redis 12.4s → 12.2s，curl 6.0s → 6.4s，SQLite 13.0s → 12.4s）。UAST 函数数下降（Redis 13,092→12,966 等）是因为配置排除的代码不再进入 UAST：逐个核对，减少的函数都在 `#if 0`、`#ifdef _WIN32`、Apple/MSVC 专用分支或 `SQLITE_ENABLE_LOCKING_STYLE`（Linux 上为 0）之内。原先“保留所有分支”时，tree-sitter 还会把 `#ifdef __cplusplus` 中的 `namespace x {` 与后面的代码错配（croaring），现在按行预处理后不再出现。
- 验证过程中 CASTLE 发现了本轮中间版本引入的两个回退，均已修复并补充回归用例：`%d` 写入格式串的数值污点被当成干净值（CASTLE-134-6，补 `real/numeric_format_index_T`）；单分支 guard 丢弃 return 分支写入时把条件本身的写入也撤销了（`if (sscanf(argv[1], "%9d", &id) != 1) return 1;`，补 `control/guard_condition_side_effect_T/F`）。
- Juliet：本轮**未重跑**。

## 4. 剩余局限

| 局限 | 说明 |
| --- | --- |
| 两分支 if 中一侧 return | `if (c) { p = x; return; } else { ... }` 中 return 分支的写入仍与另一分支合并（可能误报）；单分支 guard 已处理 |
| 后向 goto | `retry:` 形式的回跳只按顺序执行一次 |
| 缓冲区按整体建模 | 部分写入只能“保留原有 + 加入新内容”，不跟踪字节区间；指针算术得到的指针不关联原位置 |
| 系统头文件 | 不读取；项目头文件需能从包含者目录、`--cIncludeDir` 或项目根目录找到，`<x.h>` 只查 `--cIncludeDir` |
| `cover` 模式的代价 | 未决定的条件两侧都分析：覆盖多个配置，但也会报告只在某个配置下存在的问题；需要单一配置时用 `--cUnknownMacros undefined` 并给出 `--cDefine` |
| 分析失败与超时 | 单 entrypoint 时间预算（`entryPointTimeoutQuickMs`）用完后停止该入口，已产生的告警保留；被截断的入口在日志中计数，不能视为“安全” |

## 5. 复现

```bash
# 1. parser-C
cd uast/parser-C && npm test && npm run build
# 2. Engine
cd ../../engine && npx tsc --noEmit -p . && npm run test-c
# 3/6. sast-c（原 82 个 + c_semantics 78 个）
npx tsx src/main.ts --sourcePath ../workstreams/yasa-c-extension/benchmark/sast-c/case --language c \
  --ruleConfigFile ../workstreams/yasa-c-extension/benchmark/rule_config_xast_c.json \
  --checkerPackIds taint-flow-c-default --report /tmp/sast-c
python3 ../workstreams/yasa-c-extension/scripts/score_c_benchmark.py /tmp/sast-c/report.sarif \
  ../workstreams/yasa-c-extension/benchmark/sast-c/case
# 新增用例的标签核对（clang）
python3 ../workstreams/yasa-c-extension/scripts/c_semantics_oracle.py
# 7. CASTLE
python3 ../workstreams/yasa-c-extension/scripts/castle_c.py --castle <CASTLE-Source> --engine . \
  --rules resource/example-rule-config/rule_config_c.json --out /tmp/castle
```

结果文件：`results/sast-c.*`（含 c_semantics）、`results/c_semantics-before.json`（修复前基线）、`results/c_semantics-oracle.txt`、`results/independent-suite.json`（独立测试 52 + 8 逐用例修复前后）、`results/castle.*`、`results/corpus-parse.json`。

## 6. 补充修复（2026-10-29）：嵌套条件与 GNU 变参宏

对 parser-C 预处理（`018894e`）的代码审阅发现三个问题，先用独立脚本直接调用 `macros.ts` 复现，再通过完整 parser 和 Engine 确认影响，最后固定为回归用例并修复。被测版本：integration `aae29f2`、engine `c0d6004`、uast `018894e`；修复为 uast 提交 `fix(c): nested conditional state and GNU variadic macros`（只改 `parser-C/src/macros.ts`）。

| # | 问题 | 根因 | 修改 |
| --- | --- | --- | --- |
| 1 | 嵌套的未决条件组之后状态错误：外层 `#else` 中使用了从未定义的宏；组结束后宏被当作“一定已定义”，`#ifndef` 分支被整段抹空（丢代码） | 内层 `#endif` 把结果写入外层组时，外层 frame 记录的“入口值”取的是内层最后一个分支结束时的值，而不是外层组开始前的值 | 内层组结束时，外层组尚未改动的名字直接继承内层组的入口值 |
| 2 | GNU 具名变参 `args...` 只拿到第一个多余实参，其余被静默丢弃 | `args` 被当作普通形参放入 `params` | 记为 `variadicParam`，收集其余全部实参 |
| 3 | GNU `, ## __VA_ARGS__` 在变参为空时保留逗号，`LOG(buf)` 展开为 `printf(buf,)`，解析失败后退回不展开（格式串漏洞漏报）；宏体字符串字面量中的 `##` 被删除 | 粘贴运算统一用 `\s*##\s*` 删除，不区分逗号粘贴与字符串内容 | 按 GNU 语义在变参为空时去掉逗号；字面量中的 `##` 保留 |

新增 4 个语义回归用例（`c_semantics/preprocessor/`，Engine `test/c/semantics-cases/preprocessor/` 同步），标签经 clang oracle 核对：`macro_nested_conditional_ifndef_T`、`macro_nested_conditional_else_F`、`macro_gnu_named_variadic_T`、`macro_gnu_comma_paste_T`。

| 验收项 | 修复前 | 修复后 |
| --- | --- | --- |
| parser-C 单测 | 56/56（加入 2 个新单测后 2 个失败） | **58/58** |
| Engine `tsc --noEmit` | — | 0 错误 |
| Engine `npm run test-c` | 82 通过 / 4 失败（即 4 个新用例） | **86/86** |
| sast-c 全部 164 个用例 | TP 107 FN 3 TN 53 FP 1 | **TP 110 FN 0 TN 54 FP 0** |
| 其余 160 个已有用例 | 与 `results/sast-c.*` 原记录一致 | 结果不变 |
| clang oracle | — | 80/80 标签成立，2 个按设计跳过 |

运行环境：macOS arm64，Node.js v25.9.0（与 §3 的 Linux 环境不同）。逐用例修复前后见 `results/preprocessor-fix-20261029.json`。本轮未重跑 Juliet、CASTLE 和大项目解析。

审阅中另外确认但未修改的预处理局限（低优先级）：被排除区域内嵌套组的 `#else`/`#endif` 指令行未被抹空（实测 tree-sitter 可容忍，未产生解析错误或丢代码）；`#if` 求值使用 JS 32 位位运算与有符号比较（`1UL << 32`、`-1 > 0U` 结果与 C 不同）；以 `\` 续行的行注释会把下一行并入 `#define` 体。
