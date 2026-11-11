# C / C++ Parser 初期结果汇总

整理日期：2026-11-10。依据仓库既有报告整理；本次未重跑。历史结果针对各自固定版本，不能直接视为当前提交的新验收。原始报告与证据保留，本文作为阅读入口。


| 工作 | 方法与结果 | Engine |
| --- | --- | --- |
| C / C++ parser | 分别将源码转为 YASA UAST；最近一次合并前记录：C 单测 79 项、C++ 单测 27 项通过 | 不需要 |
| C 真实项目解析 | Redis、curl、SQLite 共 2,279 文件、约 119 万行；历史记录 0 崩溃，但部分文件存在语法诊断和错误恢复 | 不需要 |
| C 调用图对比 | curl 的 libcurl 构建目标，无宏直接调用函数对：Yasa 精确率 100%、召回率 99.43%；CodeGraph 99.27%、98.14% | **需要** |
| C 回调 | 精选 11 个调用点、25 条目标边：修复后 Yasa 找到 25 条，CodeGraph 找到 9 条；新增边抽查存在较多误报 | **需要** |
| C / C++ 污点分析 | C 有自建样例及 Juliet 回归；C++ Juliet 选集漏报较多 | **需要** |
| C++ 真实项目对比 | 尚未找到 C++ 大项目与 CodeGraph 的调用图准召率报告 | 尚待完成 |

数字仅适用于对应测试范围，尤其 curl 的精确率不是完整调用图精确率；回调 25 条不是全项目回调集合。单测通过也不等于语言全部支持。

## 做了什么，代码在哪里

1. **C parser**：[代码和使用说明](../uast/parser-C/README.md)。使用 `tree-sitter-c` 将 C 源码转换成 UAST，包括函数、声明、表达式和预处理相关处理。
2. **C++ parser**：[代码和使用说明](../uast/parser-CPP/README.md)。使用 `tree-sitter-cpp`，作为独立包提供接口，同时依赖 C parser、复用其 visitor 并增加 C++ 节点处理。
3. **Engine 接入**：[C 分析器](../engine/src/engine/analyzer/c/common/c-analyzer.ts)、[C++ 分析器](../engine/src/engine/analyzer/cpp/common/cpp-analyzer.ts)。负责进一步生成调用图及进行污点分析；parser 本身不等于漏洞检测引擎。
4. **混合扫描**：[实现与检查点](yasa-cpp-extension/docs/2026-11-09-c-cpp-mixed-hardening.md)。实验入口使用编译配置和 Clang 预处理，函数体仍交给 C / C++ parser。真实 zlib 目标完整数据流分析尚未在现有堆限制下完成。

## C 和 C++ 怎样转换为 UAST

两者使用独立的 Tree-sitter 语法，但共享部分预处理和 UAST 转换逻辑：

```text
C 源码   → 预处理 → tree-sitter-c   → C 语法树   → C 默认 visitor              → UAST
C++ 源码 → 预处理 → tree-sitter-cpp → C++ 语法树 → C 默认 visitor + C++ handler → UAST
```

**C parser：**调用 [Parser 接口](../uast/parser-C/src/index.ts)，先通过 `init()` 加载 C 语法，再调用 `parse()`。源码中的宏及条件编译按提供的配置处理，[macros.ts](../uast/parser-C/src/macros.ts) 中的 macros 指 C/C++ 的“宏”，不是 Mac 设备。随后 `tree-sitter-c` 生成语法树，[parser.ts](../uast/parser-C/src/parser.ts) 中的 visitor 将语法节点转换为 Yasa UAST，并记录源代码位置和解析诊断。

**C++ parser：**调用 [C++ Parser 接口](../uast/parser-CPP/src/index.ts)，由 [C++ parser.ts](../uast/parser-CPP/src/parser.ts) 加载 `tree-sitter-cpp`；普通解析入口复用 C 预处理机制，并默认定义 `__cplusplus`。它将独立的 C++ Tree-sitter parser 和 C++ handlers 传给 C 包的 `parseWithParser()`。遍历节点时，[C 的 visitor 分发入口](../uast/parser-C/src/parser.ts#L836)优先查找相应扩展 handler，否则使用 C 默认处理。C++ handlers 位于 [handlers 目录](../uast/parser-CPP/src/handlers/index.ts)，分别处理命名空间、声明和表达式等。

C++ 有自己的处理器，**没有一套完全独立的 visitor**；C 默认 visitor 目前也写在 `parser-C/src/parser.ts`，没有单独的 `visitor.ts`。由于两种语法生成的节点可能不同，共用代码不代表 C 测试自动覆盖 C++ 入口；C++ 仍须独立验证适用的共通语法。

混合扫描另有 `parsePreprocessed()` 入口：接收已由编译器预处理、移除行标记的输入，不再次运行 parser 自身预处理。普通 parser 路径和这个实验路径的配置与证据应分开记录。两条路径均可直接返回 UAST；Engine 在此之后使用 UAST 进行调用图和污点分析。

## 怎么测的

**单元测试**：直接运行 parser 包中的测试，检查特定源码的 UAST 转换；Engine 另有 C、C++ 测试。最近的 79 / 27 是合并前报告记录，不是本次实测。[检查点记录](yasa-cpp-extension/docs/2026-11-09-c-cpp-mixed-hardening.md)

**真实项目解析**：历史测试使用 Redis、curl、SQLite 的固定源码，逐文件解析，统计崩溃、诊断、UAST 函数等；这项是 parser 覆盖检查，0 崩溃不等于无语法错误或语义完全正确。[历史验收报告](yasa-c-extension/docs/C扩展-四项验收报告.md)和[解析脚本](yasa-c-extension/scripts/c_corpus_parse.ts)。后续又以包含自建语料及三个项目的 2,451 文件做 UAST 摘要回归，检查前后输出一致；这与上述 2,279 文件不是同一次统计。[C++ 工作流说明](yasa-cpp-extension/README.md)

**污点流**：使用 C 自建 `sast-c` 和 Juliet 样例，由 Engine 根据 source/sink 规则输出结果，再核对危险样例与安全对照。C++ 的 Juliet CWE-78 char 组 500 个危险例中 TP 80、FN 420；wchar_t 组同样为 80 / 420。这是特定选集的 Engine 检测结果，不是 parser 准确率。[C 工作流](yasa-c-extension/README.md)、[C++ 结果](yasa-cpp-extension/README.md)

## 怎么与 CodeGraph 比较

比较的是 **Yasa Engine 输出的调用图**和 CodeGraph 调用图，不是直接比较双方 AST。使用的真实大项目是固定版本 curl `b052c835` 的 libcurl 静态库构建目标：190 个 C 编译单元、199 个头文件；不包含命令行程序、测试及第三方依赖实现。

1. 固定源码和构建范围。Yasa 接收构建宏与头文件选项，CodeGraph v1.6.2 使用其正常源码索引入口；两者配置处理方式不同。
2. 用 Clang/libclang 分析该配置的直接调用，生成参考集：190/190 单元解析成功，提取 2,674 个项目函数定义和 6,959 对内部直接调用。此集描述编译器看到的语法调用，不保证运行时可达。
3. 选取源码中 11 个真实回调点、人工审定 25 条目标边，在查看工具结果前冻结；它是精选样本，不代表所有回调。
4. Yasa 使用 `--checkerIds callgraph --dumpAllCG` 导出调用图；CodeGraph 索引同一源码。统一文件、函数、调用位置，再与参考集逐条比较。
5. 精确率 = 正确输出 / 可评估输出；召回率 = 找到的参考边 / 参考边总数。直接调用和回调分开统计，未能归因的输出另行记录。

| curl 指标 | Yasa | CodeGraph |
| --- | ---: | ---: |
| 无宏直接调用函数对精确率 | 100%（5786 正确、0 误报） | 99.27%（5711 正确、42 误报） |
| 无宏直接调用函数对召回率 | 99.43%（漏 33） | 98.14%（漏 108） |
| 含宏完整 AST 直接调用函数对召回率 | 98.82%（6877/6959） | 83.01%（5777/6959） |
| 精选回调样本召回 | 修复后 25/25 | 9/25 |

Yasa 回调修复按结构体类型与字段汇总候选，提升召回也增加误报：抽查 20 个调用行的 121 个目标，72 正确、40 错误、9 不确定。按不确定项计错或计对，该样本精确率为 59.5%–66.9%，不能外推为整个项目精确率。报告中早期“未提交候选”是当时状态，相关修复随后已合入组件 main。

详情及评分范围：[curl 对比](yasa-c-extension/callgraph-eval/reports/02-curl-comparison.md)、[回调复测](yasa-c-extension/callgraph-eval/reports/03-curl-callback-fix-retest.md)、[误报抽查](yasa-c-extension/callgraph-eval/reports/04-callback-edge-audit.md)。评测脚本、结果及完整证据包索引：[callgraph-eval](yasa-c-extension/callgraph-eval/README.md)。完整证据与当前目录中经路径脱敏的样本文件哈希不同，复现时应核对该索引。

## 现在能做什么、还缺什么

- **不用 Engine**：运行两个 parser 单测；固定真实项目逐文件导出 UAST，统计错误、覆盖和资源；以 Clang 对照函数和可确定的直接调用结构。当前机器 parser 依赖尚需准备，C++ 包依赖并要求先构建 C parser。
- **需要 Engine**：`dumpAllCG`、污点传播、漏洞发现与 trace；可以在环境准备好后复现已有小样例及 C 调用图结果。
- **尚未完成**：C++ 真实大项目与 CodeGraph 对比；独立 parser 在当前提交和本机的完整复验；混合扫描真实目标的内存问题；C++ 类、虚函数、引用、STL 等语义完善。

`dumpAST` 是 Engine 的单文件导出入口，`dumpAllAST` 是项目批量导出入口；直接调用 parser 接口也可导出 UAST，不依赖 Engine。本次未验证当前环境的导出命令或重跑历史指标。

## 2026-11-11 本机复测与修复

使用 Engine `6916f74`、Node 22.22.1、单 worker 和同学历史固定版本的 Redis / curl / SQLite，运行 `--dumpAllAST`。首次导出 2,279 个 JSON，其中 5 个根为 `Sequence`，来自 Tree-sitter 根级 `ERROR`。修复后再次导出：2,279 个均为 `CompileUnit`，但其中 **4 个依然保留根级 `ERROR`**，不能将根类型合规等同于解析成功。

| 项目 | 文件 | 根级 ERROR | 根节点含语法诊断 |
| --- | ---: | ---: | ---: |
| Redis | 848 | 2 | 350 |
| curl | 1,071 | 1 | 271 |
| SQLite | 360 | 1 | 203 |

修复了根错误恢复时的 `CompileUnit` 返回结构、续行注释中误识别宏，以及 `#define` 中注释使 Tree-sitter 截断宏的问题。Redis jemalloc `rb.h` 在默认配置下从根级错误变为正常语法树、0 诊断。C parser 84 项、C++ parser 35 项通过。其余 4 个根级错误仍在调查，不应报告为通过。语法诊断数来自根节点 `_meta.parseErrors`，部分输出可能包含错误恢复。

使用隔离 jemalloc 源码按测试配置构建生成头文件后，GCC 预处理 `log.c` 不再出现根级错误，但预处理输出仍有 15 条语法诊断；说明构建配置有关，不能因此认为语法问题全部解决。原始首轮与最终输出、日志保存在 `artifacts/c-dumpallast-20261111/`；本轮代码为未提交工作区修改。

## 2026-11-11 C++ 真实项目探索与修复

- spdlog 固定 `6d9805df3f588402b17073dcd13eb569ceda864d`：Engine `--dumpAllAST`、单 worker，153 个文件均有 UAST；修复前后均有 122 文件带语法诊断。修复前 836 个 `template_declaration` 标为未处理；基础函数模板修复后有 416 个函数模板定义被保留，仍有 420 个模板声明未处理。限定名和成员模板调用、`this`、简单 `using` 类型别名也补充了 UAST 转换。这些是节点计数，不是语义准确率。
- Protobuf 固定 `dffe30fe36f8f6733aba5760558b3fd5e8de95e4`：整仓按 C++ 扩展名导出 1,214 个文件，445 个有诊断，18 个源自根级 ERROR；其中包含 Objective-C `.h`，不能全算 C++ 文件。首次运行约 4 分 41 秒，已包含部分中间修复，不能当作干净修复前基线。
- spdlog 的 CMake 静态库构建通过。以 GCC 按编译数据库预处理一个 C++ 单元后解析，仍有约 608 条诊断，主要涉及系统头和语言特性，不能与逐文件诊断数直接比较。配置 include 路径的整项目探索超过一小时仍未完成，手动终止；不能算成功，也不能据此给出可靠性能结论。
- C 的 GCC 预处理输入增加 `__signed__` 类型拼写兼容，curl / jemalloc 的预处理样例诊断各减少 3 条。修复和原始诊断范围见 `artifacts/cpp-dumpallast-20261111/` 及本机 `/tmp` 临时实验；未宣称支持完整编译器扩展。
- parser-C 86 项、parser-CPP 43 项通过；Engine 旧 C 112 项、C++ 62 项通过。`test-c-family` 为 50 通过、11 失败，日志显示本机缺 `/usr/bin/clang` / `clang++`；不能声称混合模式回归通过。当前代码未提交；Python 既有用户修改未纳入。

## 2026-11-11 直接脚本与 Engine 导出对照

同一份固定 Protobuf 1,214 文件清单，单 worker、相同默认预处理参数：独立脚本逐文件导出和 Engine `dumpAllAST` 均输出 1,214 个 `CompileUnit`，445 文件带诊断，逐文件诊断列表一致。去掉位置、全部 `_meta` 及 parent，并忽略 Engine 为函数/类额外增加的 `name` 后，其他 JSON 结构逐文件一致；这不是语义准确率或元数据完全一致的证明。

两种运行有并发，墙钟约 4:07（脚本）和 4:33（Engine），最大 RSS 分别约 521 MiB 和 2.99 GiB，不能视为受控速度对比；RSS 是 `/usr/bin/time` 的最大单进程值，不能直接当多进程内存总和。脚本逐文件写盘，Engine 先汇总项目结果，设计上内存使用不同；效果是否稳定还需串行复测。脚本和结果位于 `artifacts/cpp-dumpallast-20261111/compare-direct.cjs`、`compare-direct/` 与 `compare-engine/`。

后续对同一清单先后串行执行一次：Engine 4:24.78、最大 RSS 2,997,332 KiB；脚本 3:43.55、最大 RSS 506,336 KiB，均退出 0。均输出 1,214 个文件、445 个带诊断；逐文件诊断列表一致。排除位置、元数据、parent 及 Engine 额外添加的函数/类名称字段后，其余结构一致。脚本后运行、可能受缓存影响，单次计时不足以得出稳定加速比；RSS 不是多进程内存总和。日志和比较结果见 `artifacts/cpp-dumpallast-20261111/serial-*`。

其中路径属于 `objectivec/` 的头文件 80 个，41 个带诊断、3 个根级 ERROR；其余路径 1,134 个文件，404 个带诊断、15 个根级 ERROR。这只是按目录分组，不代表其余文件全部有有效的 C++ 构建配置。

非 Objective-C 路径诊断的人工抽样位置包含 `absl_nullable`、`UPB_INLINE` 和 `ABSL_ATTRIBUTE_LIFETIME_BOUND` 等项目宏附近；这只是错误片段归类，尚不能断定每处的根因。批量数据含源码快照、输出、进程日志、测试日志、parser 补丁和构建产物摘要，未提交。

对 spdlog 另做相反顺序的单次实验：脚本先运行 1.17 秒，Engine 后运行 2.33 秒；两者均输出 153 文件、122 文件带诊断，逐文件根类型与诊断列表一致。脚本最大 RSS 192,752 KiB，Engine 的 `/usr/bin/time` 最大 RSS 245,592 KiB；这不是子进程内存之和。该次只核查根类型和诊断，并非逐节点结构核验；单次测试、缓存和机器负载均限制性能结论。结果位于 `serial-spdlog-*`。

增加逐文件耗时与诊断记录的探索脚本 `profile-spdlog-direct.cjs`，可从 `profile-spdlog-direct/manifest.json` 查找文件及 UAST；本次 153 项完成，耗时最高的五项均是 bundled fmt 头文件。脚本是排障工具，最终交付仍须使用 `dumpAllAST`。

示例：`include/spdlog/fmt/bundled/base.h` 的诊断出现在 `FMT_PRAGMA_CLANG(...)`、`FMT_PRAGMA_GCC(...)`、模板别名及 `FMT_API` 附近；仅根据位置不能证明每一处都是宏导致。后续应在固定编译配置下缩小样例，并比较编译器预处理和 parser 的宏处理结果，避免直接删除宏或排除分支造成漏解析。

针对头文件处理增加确定分支上的 `#pragma once` 支持、循环包含集合与宏替换快路径；未知分支采用保守重分析，不声称完整建模所有条件路径。测试：parser-C 91 项、parser-CPP 43 项通过。指定 spdlog include 路径的完整导出在 600 秒上限后退出 124，未完成；此前超过一小时的尝试也未完成，因此目前不能声称头文件性能已解决。相关 parser 代码已提交于 UAST `1b87787`。

### C 根级错误：隔离研究（2026-11-11）

研究阶段只在 `/tmp/yasa-c-grammar-experiment` 中修改和构建实验语法；随后已集成位域部分，四个文件的根级错误仍未修复。底层基线为 `tree-sitter-c` 0.23.6，实验用 tree-sitter-cli 0.25.10 和本机 Docker 中的 Emscripten 4.0.4 生成 WASM。两版通过相同 `parseWithParser` 调用和配置比较。

- 条件编译：`int a[] = { 1,\n#ifdef FEATURE\n2,\n#endif\n3 };`（此处 `\n` 表示换行）在 `unknownMacros: cover` 下报告 `#ifdef` 和 `#endif` 两处语法错误；FEATURE 的配置已知时能选择相应分支。默认保留未知分支时，不能仅靠选定一个分支来声称解析了所有配置。Redis 的 `deps/tre/lib/tre-parse.c` 包含类似结构。
- 匿名位域：合法代码 `struct S { int :32; };` 在现有语法中报错。实验将语法的 `_field_declaration_declarator` 扩展为允许单独的 `bitfield_clause`，最小例子不再报语法错误。但现有 visitor 对没有声明名的位域返回 `Noop`，还需要设计并验证位宽在 UAST 的表示，不能把零语法错误等同于完整翻译。
- 对已有 GCC 预处理文件复测（并非 `dumpAllAST` 端到端结果）：curl OpenSSL 从 13 个诊断降至 2 个，jemalloc log 从 12 个降至 1 个。剩余的 curl 诊断是 `__attribute__((fallthrough))`，jemalloc 诊断位于 `__builtin_va_arg(ap,const char *)`。这些预处理输入位于 `/tmp/yasa-curl-openssl.i` 和 `/tmp/yasa-jemalloc-log.i`，为之前实验生成的临时文件；本次未重建，不能据此断言它们代表所有构建配置。
- 对四个未预处理原始文件使用默认配置复测，实验语法未改变结果：Redis tre `ERROR/28`、jemalloc log `ERROR/30`，curl OpenSSL `ERROR/50`，SQLite os_win `ERROR/114`（格式为 Tree-sitter 原始根类型/诊断数）。因此匿名位域修改本身不解决当前四个根级错误。

位域实验语法的核心改动如下（随后已集成并进行下述验证）：

```js
_field_declaration_declarator: $ => commaSep1(choice(
  seq(field('declarator', $._field_declarator), optional($.bitfield_clause)),
  $.bitfield_clause,
)),
```

随后对位域的 UAST 表示、语法 WASM 的维护及 C/C++ 回归与 `dumpAllAST` 做了下述验证；条件分支表示仍待解决。

### C 位域修复与 dump 验证（2026-11-11）

C parser 已集成本地 C 语法的匿名位域规则，并在 UAST 元数据中保留匿名及命名位域的位宽；匿名位域不计入结构体初始化成员。语法来源、许可证与重新生成方式记录在 `uast/parser-C/grammar/README.md`。C 单测 92 项、C++ 单测 43 项通过。

使用 Engine `--dumpAllAST` 测试了一个位域小样本和上述四个真实项目文件，均产生输出：位域小样本零语法诊断且含位域信息；四个真实文件仍分别为根 `ERROR`，诊断数 28、30、50、114。因此这项修复改善的是位域处理，并未解决四个原始文件的根级错误。已有 GCC 预处理文件用正式集成的 parser 复测为 curl 2 个诊断、jemalloc 1 个诊断。此次只验证五个文件，并未重新全量测试三个项目。

条件编译的实验语法可使带 `#ifdef/#else` 的初始化列表语法通过，但现有 UAST 转换会将两条分支当作一个顺序数组项，后续元素的下标可能错误；该实验未集成，需要先设计能够保留各分支及其各自位置的表示。
