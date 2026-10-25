# C 语言扩展：四项验收报告

日期：2026-10-25。实现说明见 [设计与实现](C扩展-设计与实现.md)。

## 结论

| 验收项 | 结果 |
| --- | --- |
| 1. 功能单测 | parser-C 50/50 通过；Engine `npm run test-c` 3/3 通过；Engine 全量 `tsc --noEmit` 0 错误 |
| 2. 靶场语义流通（自建 xAST 风格 sast-c，82 例） | 65/65 正例检出，17/17 反例无误报 |
| 3. 大项目解析（Redis、curl、SQLite，2,279 文件、119 万行） | 0 崩溃、0 构建错误；UAST 函数数 ≥ tree-sitter 函数数（100.2%–100.9%）；curl 命令行工具完整扫描 2 分 42 秒完成 |
| 4. 真实靶场命中率 | Juliet CWE-78、CWE-134（char 与 wchar_t，共 6,080 个测试用例）：TPR 100%，FPR 0%；CASTLE 污点类 CWE：TPR 100%，安全样本 FPR 62.5%（输入校验类写法，见 4.2） |

需要注意的是：sast-c 和实现由同一人编写；Juliet 的 char 用例在开发中被用来发现问题（修复的都是通用 C 语义，见 4.1）。wchar_t 用例在修复前作为留出集跑过一次，结果和修复内容如实记录在 4.1。

## 环境与固定版本

| 项 | 值 |
| --- | --- |
| 运行环境 | Linux x86_64，4 核，Node.js v22.22.0 |
| tree-sitter | `tree-sitter-c` 0.23.6，`web-tree-sitter` 0.26.9 |
| yasa-uast | 开发与验收基于 `dbfc7eb`；提交前迁移到 `ebd02b8`（main `6ce320b` 固定的版本）+ C parser 提交 `e748bc4` |
| yasa-engine | 开发与验收基于 `79cbc0a`；提交前迁移到 `ed717ed` + C 分析提交 `72283a7` |
| 复测 | 迁移后在新基线上重跑 parser 单测、Engine 测试、sast-c、Juliet 四个集合与 CASTLE，结果与下文完全一致 |
| 规则 | `engine/resource/example-rule-config/rule_config_c.json`；sast-c 使用 `benchmark/rule_config_xast_c.json`（同一规则 + `taint_src`/`taint_sink`） |
| Juliet | `arichardson/juliet-test-suite-c` @ `f88433e3443648a17671398797a04ea1f8e1a274`（NIST Juliet C/C++ 1.3 的 C 部分） |
| CASTLE | `CASTLE-Benchmark/CASTLE-Source` @ `765376ec24989f69a5ad523222784aa9d02cc6af` |
| Redis / curl / SQLite | `ad49ff0d` / `1f0346f0` / `9626d89e`（各自默认分支浅克隆） |

## 1. 功能单测

```bash
cd uast/parser-C && npm test          # 50 passing
cd engine && npm run test-c           # 3 passing
cd engine && npx tsc --noEmit -p .    # 0 errors
```

parser 单测按类别覆盖：编译单元与位置、声明（多声明符、存储类、原型、函数指针、struct/union/enum、typedef、声明符由内向外）、函数、语句、表达式、初始化列表（下标/字段键、指定初始化器、复合字面量）、字面量（13 种数字写法、转义、拼接）、预处理（头文件保护、全分支、宏展开、平台分支选择、`#`/`##`/`__VA_ARGS__`、递归保护）、容错（指针赋值、`#ifdef` 中的 case、语句表达式、ERROR 恢复、strict 模式）、码医生的 `vulnerable.c`。

Engine 回归测试扫描 `engine/test/c/checker-cases/`（8 个文件），断言恰好报出 9 个漏洞 sink 位置，且安全写法不报。

## 2. 靶场语义流通（sast-c）

xAST 没有 C 版本，因此按 xAST 的格式自建了 `benchmark/sast-c`，说明见 [benchmark/README.md](../benchmark/README.md)。

| 类别 | TP | FN | TN | FP |
| --- | ---: | ---: | ---: | ---: |
| accuracy/context_sensitive | 9 | 0 | 2 | 0 |
| accuracy/field_sensitive/array | 3 | 0 | 2 | 0 |
| accuracy/field_sensitive/struct | 8 | 0 | 2 | 0 |
| accuracy/flow_sensitive | 9 | 0 | 3 | 0 |
| completeness/cross_file | 4 | 0 | 0 | 0 |
| completeness/expression | 6 | 0 | 3 | 0 |
| completeness/libc_propagation | 9 | 0 | 2 | 0 |
| completeness/pointer | 5 | 0 | 1 | 0 |
| completeness/preprocessor | 5 | 0 | 0 | 0 |
| real_api | 7 | 0 | 2 | 0 |
| **合计** | **65** | **0** | **17** | **0** |

开发过程中的变化：第一次运行时 recall 为 88.5%（54/61），FPR 为 18.8%（3/16）。漏报来自嵌套成员写入、指针写回、头文件内联函数、标签语句、宏；误报来自初始化列表不区分下标、`return` 之后的代码、`if (0)`。逐项修复后达到上表结果，并为 Juliet 中发现的问题补充了 5 个用例。

## 3. 大项目解析

```bash
cd uast/parser-C
npx tsx ../../workstreams/yasa-c-extension/scripts/c_corpus_parse.ts \
  [--dump OUT_DIR] --json result.json <redis> <curl> <sqlite>
```

| 项目 | 文件 | 行数 | 崩溃 | 构建错误 | 含 tree-sitter 语法错误的文件 | 函数（UAST / tree-sitter） | 宏展开次数 | 解析耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Redis | 848 | 424,617 | 0 | 0 | 397 | 13,092 / 13,002 | 14,909 | 12.4 s |
| curl | 1,071 | 302,730 | 0 | 0 | 282 | 5,905 / 5,853 | 5,550 | 6.0 s |
| SQLite | 360 | 462,778 | 0 | 0 | 216 | 9,978 / 9,963 | 24,287 | 13.0 s |

- **语法错误文件多**：tree-sitter 看到的是未预处理的源码，遇到 `SQLITE_API`、`CURL_EXTERN` 这类宏时会产生 ERROR 区域。parser 会记录这些错误，并从 ERROR 区域中恢复完整的函数和声明，所以函数没有丢失。
- **函数数略多于 tree-sitter**：多出来的是宏展开生成的函数定义，以及 `#if/#else` 两个分支各自定义的同名函数。
- **ERROR 恢复的作用**：恢复前 SQLite 只保留 96.7% 的函数（例如 `vdbeapi.c` 中一个跨 1,400 行的 ERROR 区域吞掉了其中所有 `#ifdef` 块）；恢复后为 100%。
- **未处理节点**：只剩 `gnu_asm_expression`（内联汇编）和 `macro_type_specifier`，合计不到 120 处。
- **dump**：`--dump` 会把每个文件的 UAST 写成 JSON，三个项目共约 2.2 GB。Engine 自带的 `--dumpAllAST` 对 C 同样可用。

### 3.1 Engine 全流程扫描

用默认 C 规则对 curl 命令行工具（`curl/src`，88 个文件、23,720 行）做一次完整的污点扫描，用来检查 Engine 在真实项目上能否跑完：

| 指标 | 值 |
| --- | --- |
| 总耗时 | 2 分 42 秒（解析 2.5 s，调用图 25.6 s，符号执行 2 分 12 秒） |
| 峰值 RSS | 约 773 MB |
| entrypoint | 38 个（调用图根函数） |
| 标记的 source / 命中的 sink | 181 / 32 |
| 告警 | 0 |

`operate`（curl 从 `argv` 开始的主处理函数）调用树很深，用满了 2 分钟的单 entrypoint 时间预算后被截断。所以“0 告警”只能说明扫描能在真实项目上完成且没有噪声，不能说明 curl 经过 `operate` 的路径都分析完了。没有时间预算时，这一个 entrypoint 跑了 20 分钟以上也没结束，因此给 CAnalyzer 加上了与 Java 分析器相同的时间预算（`entryPointTimeoutQuickMs`）。大项目的深调用树分析效率是后续需要优化的方向。

## 4. 真实靶场命中率

### 4.1 NIST Juliet（CWE-78 命令注入、CWE-134 格式化字符串）

```bash
python3 scripts/juliet_c.py run   --juliet <juliet> --cwe CWE78_OS_Command_Injection --variant char \
        --engine engine --rules engine/resource/example-rule-config/rule_config_c.json --out <out>
python3 scripts/juliet_c.py score --juliet <juliet> --cwe CWE78_OS_Command_Injection --variant char --out <out>
```

每个测试用例都包含一个 bad 流程和若干 good 流程（goodG2B、goodB2G）。按 Juliet 惯例以测试用例为单位计分：sink 落在 `bad*` 函数内的告警计为 TP，落在 `good*` 函数内的计为 FP。多文件用例（51–54、61–68 等流程变体）放在同一批次里分析。Juliet 中 CWE-23/36（路径穿越）只有 C++ 用例，所以没有纳入。

| 集合 | 测试用例 | C 文件 | TP | FN | TN | FP | TPR | FPR | 分析耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CWE-78 char | 1,900 | 2,800 | 1,900 | 0 | 1,900 | 0 | 100% | 0% | 124 s |
| CWE-78 wchar_t | 1,900 | 2,800 | 1,900 | 0 | 1,900 | 0 | 100% | 0% | 126 s |
| CWE-134 char | 1,140 | 1,680 | 1,140 | 0 | 1,140 | 0 | 100% | 0% | 145 s |
| CWE-134 wchar_t | 1,140 | 1,680 | 1,140 | 0 | 1,140 | 0 | 100% | 0% | 138 s |

覆盖 5 种 source（connect_socket、listen_socket、console、file、environment），10 种命令注入 sink（含 Windows `_spawn*`/`_exec*`）与 6 种格式化字符串 sink，以及 38 种控制流/数据流变体（01–68）。

开发过程（char 用例）：

| 阶段 | CWE-78 TPR | CWE-134 TPR | FP | 当时发现并修复的问题 |
| --- | ---: | ---: | ---: | --- |
| 首次运行（前 100 例） | 0% | — | 0 | 规则 `"0:"` 只匹配第 0 个参数；`do { recv(...) } while (0)` 循环体被跳过；`recv(s, (char *)(data + n), ...)` 的污点没落到 `data` |
| 修复后（前 100 例） | 95% | — | 0 | 联合体成员共享存储；跨文件 `extern` 全局变量 |
| 第一次全量 | 32.0% | 80.0% | 0 | `strncat(data + n, env, ...)` 的输出缓冲区；Windows CRT sink；打分脚本中 `w32` 前缀归属 |
| 第二次全量 | 99.5% | 99.5% | 18 | 两个指针指向同一变量时读到旧值（流程 32）；`while (1) { ...; break; }` 被展开两轮、if/else 顺序执行，导致 `strncat` 的长度参数被判为污点 |
| 最终 | 100% | 100% | 0 | — |

wchar_t 留出集：修复前跑过一次，CWE-78 为 80%（environment 来源 0%），CWE-134 为 0%，FP 均为 0。原因都是缺少宽字符 API：输出参数模型没有 `wcsncat`，规则没有 `wprintf` 系列 sink 和 `_wgetenv`。补上这些 API 后得到上表结果，分析逻辑没有改动。

### 4.2 CASTLE

```bash
python3 scripts/castle_c.py --castle <CASTLE-Source> --engine engine \
  --rules engine/resource/example-rule-config/rule_config_c.json --out <out>
```

CASTLE 有 25 个 CWE，每个 10 个独立程序（6 个有漏洞、4 个安全）。每个文件单独运行一次 Engine（它们都定义 `main`，放在一起会互相解析到对方的函数），按文件计分。

| 范围 | TP | FN | TN | FP | TPR | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 污点类 CWE（78/134/22/89） | 24 | 0 | 6 | 10 | 100% | 62.5% |
| CWE-78 命令注入 | 6 | 0 | 1 | 3 | 100% | 75% |
| CWE-134 格式化字符串 | 6 | 0 | 3 | 1 | 100% | 25% |
| CWE-22 路径穿越 | 6 | 0 | 0 | 4 | 100% | 100% |
| CWE-89 SQL 注入 | 6 | 0 | 2 | 2 | 100% | 50% |
| 其余 21 个 CWE（内存安全、并发、整数、资源等） | 4 | 122 | 83 | 1 | 3.2% | 1.2% |

- **污点类漏报为 0**。
- **安全样本的误报**都来自程序自己写的输入校验：逐字符白名单（`isalpha`/`isdigit`）后提前 `return`、检查 `..` 或 `/`、`realpath` 后比较前缀、清空 `argv[1]` 等。纯污点分析不推理这些分支条件，所以仍会报出。引擎支持在 ruleconfig 里按项目配置 sanitizer（如把校验函数配置为 `VALIDATE_BY_FUNCTIONCALL`），但 CASTLE 每个文件的校验写法都不同，这里没有为它定制。
- 数值转换（`atoi`/`strtol`）作为注入类 sink 的屏障后，CWE-78 有 1 个安全样本不再误报。
- **其余 CWE** 不是污点分析的检测目标，检出率低是预期结果。命中的 4 个来自 strcpy 源参数被污染（CWE-787）等规则的附带覆盖；误报仅 1 个。

## 5. 已知局限

见 [设计与实现 §4](C扩展-设计与实现.md#4-已知局限)。对验收结果影响最大的两点：

1. 没有路径敏感的值分析，带输入校验的安全写法仍会被报出（CASTLE 安全样本）；
2. 宏只在本文件内展开，定义在头文件里的宏不会展开。
