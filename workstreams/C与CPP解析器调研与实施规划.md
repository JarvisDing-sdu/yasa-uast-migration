# C/C++ Parser 阶段报告

更新于 2026 年 11 月 17 日。

## 1. 当前结果

**11 月 17 日增量**：修复依赖类型运算符赋值被整条丢弃的问题。spdlog 恢复 294 条赋值、343 条调用表达式和 287 条一元运算记录，旧结构无减少；仍保留 294 次 `dependent_assignment_target` 诊断。jsoncpp 3、spdlog 7 个单元正式 dump 均成功，partial 数未下降。联合回归 **359 项通过**，类型检查通过。其余四项目本轮未重跑，下表是 11 月 16 日完整基线。[增量验收记录](yasa-cpp-extension/results/clang-parser-20261115/dependent-assignment-20261117.json)。

**11 月 16 日完整基线：Clang 路线已完成六个真实项目、523 个编译单元的正式 dump 验收：全部导出，根节点均为 CompileUnit，语法诊断 0。358 项联合回归通过，TypeScript 检查通过。**

| 项目 | 编译单元 | 导出成功 | 部分转换（partial） |
| --- | ---: | ---: | ---: |
| curl | 196 | 196 | 11 |
| sqlite | 102 | 102 | 16 |
| jsoncpp | 3 | 3 | 3 |
| spdlog | 7 | 7 | 7 |
| ncnn | 200 | 200 | 192 |
| zlib | 15 | 15 | 1 |
| **合计** | **523** | **523** | **230** |

### 本轮补齐了什么

- **结构与常量**：修复较大枚举常量误判；保留模板参数包展开中的表达式和调用；保留嵌套 case 子结构。参数包和嵌套跳转仍明确标记未完整支持。
- **C++ 语义**：支持简单标量值捕获快照、重复创建闭包、mutable 修改隔离、无成员遮蔽的非虚单继承、命名空间别名。复杂捕获和继承仍保留诊断。
- **C 控制流与初始化**：包含前几轮有界数组补零、简单后向跳转、switch 前置声明及标签修复；新增有界 GNU case 区间转换，以及共用分析器中的字面量 switch 选择和贯穿。

六项目按“函数／调用名称＋原始文件＋起始行”比较，旧函数和调用记录未减少。jsoncpp 恢复 3 条、spdlog 恢复 92 条调用记录；ncnn 的 3,800 次重复枚举值误判已消除；这些是结构记录，不能据此推算调用图准召率。诊断变化及完整命令见[本轮验收记录](yasa-cpp-extension/results/clang-parser-20261115/semantic-round-20261116.json)。

**验收边界**：使用 Linux、Clang 21.1.8 和固定编译数据库；ncnn 为关闭 Vulkan、OpenMP、运行时 CPU 分派和 AVX 的 CPU 构建。partial 表示仍有语义缺口，成功导出不等于完整支持。本轮大项目使用正式 dump，另用小样例验证 Engine 对捕获和分支的消费；未重新评测完整项目调用图或 CodeGraph，历史 spdlog 完整分析超时仍待解决。

此前两路线对照中，curl、SQLite、jsoncpp、spdlog 的 308 个单元均可导出；Tree-sitter 的 jsoncpp、spdlog 分别有 9、185 条语法诊断，Clang 均为 0。本轮未重跑 Tree-sitter。独立 C++ parser 的 54 项通过属于此前测试，与本轮 358 项不是同一测试集。

## 2. 源码到 UAST 的两条路线

### 共同输入与预处理

Clang、GCC 都是支持 C/C++ 的编译器工具。`-E` 要求完成预处理后停止，输出展开后的源码文本。两条配置化路线都从 `compile_commands.json` 读取每个编译单元的真实构建参数，再进行预处理。

| 概念 | 在本流程中的具体含义 |
| --- | --- |
| 构建配置 | 当前源文件的语言标准、宏定义、头文件搜索路径等。例如 `clang -std=c11 -DUSE_FAST -Iinclude -Ibuild -c main.c` 启用 `USE_FAST`，并指定两个头文件目录 |
| 宏展开 | 将 `#define CALL(x) target(x)` 对应的 `CALL(value)` 展开为 `target(value)`。复杂宏还能生成声明、分支和循环 |
| 条件编译 | 根据源码、头文件及命令行中的宏，选择 `#if/#ifdef` 当前成立的分支。定义 `USE_FAST` 时可保留 `fast()`，另一配置可保留 `slow()` |
| 编译单元 | 一个源文件及其 include 内容经过预处理得到的一份输入。同一源文件的不同编译参数可形成不同的处理记录 |

这里处理的是当前配置实际启用的代码。项目自己的 `config.h` 可能由构建过程生成，因此需要使用匹配的构建目录和头文件路径。多配置语义合并尚待实现。

### 路线一，编译器预处理＋Tree-sitter visitor

对应 `--cCompileCommands … --cAstBackend tree-sitter`，语言由 `--language c` 或 `--language cpp` 指定。

```text
源码＋编译参数 → Clang/GCC -E → 带行标记的完整预处理文本
  → 建立 sourceMap，行标记及系统头区域空白占位
  → Tree-sitter 语法树 → C visitor / C++ handlers → 项目 UAST JSON
```

| 步骤 | 处理代码 | 输入与处理 | 得到的结果 |
| --- | --- | --- | --- |
| 1. 选择编译配置 | [compiler-dump.ts][dump]、[compilation-database.ts][database]、[build-selection.ts][selection] | 读取源码路径和编译数据库，选定命令，提取语言、标准、宏及头文件路径 | 当前单元的构建上下文，含 `entryId` 与编译参数 |
| 2. 编译器预处理 | [compiler-dump.ts][dump] 调用 [compiler-preprocess.ts][preprocess] 的参数整理逻辑 | 将源码与所选参数交给 Clang/GCC 的 `-E`，展开宏、选择条件分支、展开 include | 标准输出中的完整预处理文本，暂存在内存 |
| 3. 整理待解析文本 | [source-map.ts][source-map] 的 `decodeLineMarkers`、`projectText` | 从行标记建立来源映射，再将标记和系统头区域替换为空白，保留项目头内容及当前源文件 | 供 parser 读取的文本及 `sourceMap`，保留预处理文本的行数和字符列位置 |
| 4. 按语言生成语法树 | [parser-CPP/src/index.ts][unified] 分发到 [parser-C/src/parser.ts][c-parser] 或 [parser-CPP/src/parser.ts][cpp-parser] | `parsePreprocessed` 接收整理后的文本。C 加载 `grammar/tree-sitter-c.wasm`，C++ 加载依赖包中的 `tree-sitter-cpp.wasm`，调用 Tree-sitter 解析 | 语法树及语法错误位置 |
| 5. visitor 转换 | C 使用 [parser-C/src/parser.ts][c-parser] 的 `visit`。C++ 通过 [handlers/linkage.ts][linkage]、[handlers/index.ts][handlers] 接入声明、表达式、命名空间和语句处理，并复用 C 公共 visitor | 将函数、变量、调用和分支、循环、跳转等控制流结构映射为 UAST | 根节点为 `CompileUnit` 的 UAST，附带 `parseErrors` 和未支持结构记录 |
| 6. 定位并导出 | [compiler-dump.ts][dump]、[deep-json.ts][deep-json] | 查询 `sourceMap` 补充原始文件起始行，附加编译配置与状态，序列化 JSON | 单文件输出到 `--report` 指定文件。批量输出为 `<entryId>.json` 和 `manifest.json` |

WASM 提供语法规则，TypeScript visitor 负责生成 UAST。配置化入口使用 `parsePreprocessed`，普通 `parse()` 入口中的本地宏处理由 `parser-C/src/macros.ts` 承担。

**空白占位的两项作用需要分别理解。** 行标记先转成来源映射，再用空白占位，使后续节点位置与映射保持对应。系统头区域的屏蔽则是当前实现控制输入规模、减少扩展语法处理负担的取舍，Tree-sitter 可以接收包含系统头的文本。系统头身份依据编译器行标记判断。

屏蔽系统头也会移除 `size_t`、`FILE`、标准库模板等声明上下文，影响后续类型解释及转换完整性。现有 C++ 语法诊断中有多少与屏蔽有关，需要保留／屏蔽系统头的对照实验验证。

### sourceMap 怎样追溯源码位置

编译器输出中的 `# 8 "/project/main.c" 2` 表示后续代码回到 `main.c` 原始第 8 行。`decodeLineMarkers` 将这些标记整理成连续区段。下面是简化的映射记录。

```json
{
  "generatedStartLine": 100,
  "generatedEndLine": 120,
  "origin": { "file": "/project/main.c", "line": 30, "system": false }
}
```

该记录表示预处理文本第 100～120 行对应 `main.c` 原始第 30 行开始的内容。节点位于预处理文本第 105 行时，`mapOrigin` 二分查找所属区段，再计算原始行号 `30 + (105 - 100) = 35`，将文件名和第 35 行写入节点的 `_meta.originalLocation`。实际记录还区分物理文件与编译器报告的文件位置，以处理 include 和 `#line`。

两条路线都使用这种文件、行号映射。宏展开可能改变 token 数量和长度，当前原始列号标记为未知，逐 token 的宏定义／调用来源映射尚待实现。

### 路线二，Clang AST＋UAST 适配器

对应 `--cCompileCommands … --cAstBackend clang`，编译数据库中的命令需要使用 Clang。C 与 C++ 共用适配器，通过语言模式区分。

```text
源码＋编译参数 → Clang -E → 带行标记的完整 .i / .ii
  → Clang 利用完整头文件上下文解析并进行语义分析 → Clang AST JSON
  → 筛选项目节点 → 我们的适配器 → 项目 UAST JSON
```

| 步骤 | 处理代码 | 输入与处理 | 得到的结果 |
| --- | --- | --- | --- |
| 1. 选择编译配置 | [compiler-dump.ts][dump]、[compilation-database.ts][database]、[build-selection.ts][selection] | 读取源码路径和编译数据库，选定当前单元的 Clang 命令与语言模式 | 构建上下文，含宏、头文件路径、语言标准和 `entryId` |
| 2. 生成预处理文件 | [compiler-preprocess.ts][preprocess] 的 `preprocessUnit`、[source-map.ts][source-map] | 执行依赖检查和 Clang `-E`，展开宏、条件分支及头文件，保留完整内容并建立来源映射 | 临时目录中的 C `unit.i` 或 C++ `unit.ii`，以及依赖、源码映射记录 |
| 3. 生成编译器 AST | [compiler-preprocess.ts][preprocess] 的 `readDeclarationMetadata`、[compiler-json.ts][compiler-json] | Clang 读取完整 `.i/.ii`，执行 `-fsyntax-only -Xclang -ast-dump=json`。输出流在落盘时压缩格式空白 | 临时 `compiler-ast.json`，包含声明、引用、类型和函数体节点 |
| 4. 读取并选择节点 | [compiler-declarations.ts][declarations] 的 `readCompilerDeclarations` | 严格校验并流式读取 AST JSON，提取声明和引用，按源位置向转换器交付项目声明子树 | 声明元数据与项目 AST 子树，元数据保存为 `declarations.json` |
| 5. 适配为 UAST | [clang-uast.ts][clang-uast] 的 `ClangUastConverter.add/visit/finish`，字符串解码使用 [clang-string.ts][clang-string] | 将 Clang 节点映射为 UAST，利用声明引用、类型等信息处理默认实参、归属类和源码位置，记录语义缺口 | `CompileUnit` UAST，附带 `clangBackend.unsupported` 和转换状态 |
| 6. 导出 | [compiler-dump.ts][dump]、[deep-json.ts][deep-json] | 补充导出元数据并序列化 UAST | 单文件 UAST JSON，或批量 `<entryId>.json` 与 `manifest.json` |

**两条路线的主要差异在解析和筛选的顺序。** Tree-sitter 路线先屏蔽系统头区域再解析，后续由 visitor 承担结构转换与相关解释。Clang 路线先利用完整头文件上下文完成语法、类型和声明关系分析，再筛选需要转换的节点。C++ 的模板、重载、构造函数和 lambda 会影响类型、调用目标及隐式调用，Clang 已提供更多相关信息，我们继续负责正确的 UAST 映射。

编译器 AST JSON 的格式空白压缩保留字符串和节点内容，减少序列化排版占用。配置化 dump 的第 4、5 步在同一遍流式读取中完成。`.i/.ii` 和编译器 AST 位于临时目录，单次 dump 结束后自动清理。最终保留 UAST JSON 与批量 manifest。

### 与“大语义树”、跨文件关联和函数内联的关系

当前已经实现按所选配置展开编译单元，并导出项目 UAST。例如 `main.c` 包含 `config.h`、`api.h`，展开后共同参与该单元的解析；`worker.c` 独立形成另一个编译单元。

| 层次 | 具体操作 | 当前状态 |
| --- | --- | --- |
| 编译单元内展开 | 展开 include、宏和当前成立的条件分支，再生成 AST/UAST | 已跑通，转换完整性继续补齐 |
| 项目级语义关联 | 将 `main.c` 的调用／声明关联到 `worker.c` 的定义，并保留单元配置、类型和链接身份 | 分析入口已有跨单元符号索引，继续验证。单独 dump 逐单元导出 |
| 多配置语义合并 | 同时保留 `USE_FAST` 开启、关闭时的代码，并为节点或关系记录成立条件 | 待实现 |
| 函数体内联 | 在调用位置展开被调函数体，处理实参、局部作用域、递归与代码增长 | 当前通过调用及定义关系表达，按需内联方案待设计 |

从“大语义树”的目标看，当前完成了编译单元展开这一层。后续可沿“每单元保留树、项目级索引连接各树”的结构推进，保留重复头文件、同名 `static` 函数及不同宏配置各自的身份。缓存与增量更新可围绕编译参数和依赖文件校验设计，具体策略仍待实现与测量。

### UAST 怎样交给 Engine

`dumpAST/dumpAllAST` 完成解析和导出。调用图及污点分析通过 [c-family-runner.ts][runner] 的分析入口运行，使用 `--astBackend tree-sitter` 或 `--astBackend clang`。

分析入口先读取声明元数据、选取所需的系统包装函数，再由 [c-family-ast-builder.ts][builder] 调用对应 parser 或 `convertClangAstFile`，绑定编译器符号并调用 `processParsedAst`，供现有 C-family 分析器消费。Clang 分析路径保留单独的转换遍历。当前统一 parser 门面位于 `parser-CPP` 包，内部继续依赖 `parser-C`。

### 本轮解决的问题

- **Clang 初始化与赋值结构**。保留编译器提供的默认实参子树，修复类型别名构造的默认实参查找，补齐标准初始化列表和依赖括号初始化中的操作数。引用返回调用用作赋值左侧时保留完整赋值与两侧调用，写回目标语义继续保留诊断。
- **真实构建参数兼容性**。正式 dump 入口支持 ncnn 使用的 `-ffast-math`、`-fvisibility-inlines-hidden`、SSE 和 `-mrecip=none` 参数。双路线单测验证参数保留、条件分支选择及无目标文件副产物。

- **Tree-sitter C++ 结构**。保留 lambda 参数、显式返回类型、函数体和捕获信息，补齐类内及类外构造函数定义标记。构造函数所属类型从语法树及限定名识别，原有 struct 字段转换流程保留。jsoncpp 恢复 3 个 lambda 函数体，既有函数记录无减少，并记录 86 条构造函数定义标记。捕获和构造初始化列表的完整语义仍待补齐。

- **跨项目导出失败**。jsoncpp 首次验收暴露 `->*` / `.*` 成员指针运算符无法交给普通二元表达式构造器。现改为保留操作数和访问结构，并记录 `member_pointer_resolution`，避免单个运算符中断整个编译单元导出。

- **C 转换缺口**。补齐安全取值范围内的枚举整数转换、复合字面量、变参读取、静态 `offsetof`、GNU 语句表达式及其内部类型检查。保留语句表达式的局部作用域和结果，验证变量遮蔽与外层赋值。curl 的 partial 从 100 降至 16，12,885 条函数定义记录与修复前逐单元核对一致。

- **调用与控制流**。恢复项目函数、方法和构造函数的默认实参及字段默认初始化，验证显式实参覆盖、简单 lambda 引用捕获读写和前向 goto。
- **结构与数据保留**。修复类外定义归属、模板构造函数遗漏、透明包装丢弃 throw，以及字符串、宽字符数字表的转换。curl 的空汇编得到明确表示，实际指令和 clobber 继续保留诊断。
- **跨单元符号**。区分模板声明与实例化，识别隐式 inline。正文一致的合法重复定义可合并，冲突正文和普通重复定义仍被拒绝。
- **数据处理**。配置化 dump 将声明提取与项目节点转换合为一次遍历，编译器 JSON 在落盘时流式压缩格式空白。真实样本优化前后的 metadata 和 UAST 校验一致。

### 上轮性能变化

同一源码和编译配置，各运行三次取中位数，包含预处理、转换和导出。

| 样本 | 优化前 | 上轮优化后 | 耗时下降 |
| --- | ---: | ---: | ---: |
| curl altsvc.c | 1.53 秒 | 1.25 秒 | 18.3% |
| curl openssl.c | 3.71 秒 | 2.60 秒 | 29.9% |
| spdlog.cpp | 24.40 秒 | 13.90 秒 | 43.0% |
| async.cpp | 9.98 秒 | 6.10 秒 | 38.9% |

`async.cpp` 的中间 AST JSON 从约 320 MB 减至 117 MB。`spdlog.cpp` 的峰值 RSS 中位数从约 660 MiB 降至 541 MiB，两个 C 样本的峰值 RSS 略有增加。

## 3. 剩余问题与推进顺序

继续限定现有六项目，以“最小正反例 → 原文件 → 固定目标全量复测”推进。

| 顺序 | 工作 | 验收重点 |
| --- | --- | --- |
| 1 | 保留其他未转换节点的有效子结构，区分模板定义与具体实例 | 不丢函数、调用、初始化及副作用；未解决语义继续诊断 |
| 2 | C 的一般 goto、嵌套 case 分派及聚合初始化 | 核对跳转路径、作用域和求值次数 |
| 3 | C++ 对象／混合捕获、复杂继承、模板及对象生命周期 | 分别验证结构与 Engine 消费，避免把节点存在当成语义正确 |
| 随后 | 原子内存语义、完整 Engine 超时与调用图对比 | 固定参考集后报告准召率、时间和内存 |

本轮未开展专项性能对比；多配置语义合并仍待实现。

## 4. 代码、命令与实验材料

本轮配置为本机 `artifacts/clang-session-30min-20261115/project-stability-config.json`；五项目结果在 `semantic-round-fixed/`，ncnn 结果在 `ncnn-semantic-round-20261116/`（均位于同一目录）。完整 UAST 已压缩并校验，测试日志在 `artifacts/semantic-round-20261116/`。

跨项目脚本为 `workstreams/yasa-cpp-extension/scripts/parser_acceptance.py`，调用正式 `dumpAllAST`；ncnn 逐单元调用正式 `dumpAST`。本轮摘要保留完整命令、源码哈希、诊断变化和结构对照。实现位于独立工作区 `/home/jarvis/文档/projects/yasa-c-family-experiment/engine`，分支为 `codex/c-family-pilot-20261115`；本轮同时修改 `clang-uast.ts`、共用 `c-analyzer.ts` 和两份 Clang 回归测试。

| 查阅内容 | 入口 |
| --- | --- |
| Clang AST→UAST 转换 | [clang-uast.ts][clang-uast] |
| 预处理、AST 读取和符号处理 | [Engine C-family 源码目录](https://github.com/JarvisDing-sdu/yasa-engine/tree/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family) |
| dump 与分析命令说明 | [Engine C-family 文档](https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/docs/c-family.md) |
| 最小样例和集成测试 | [test/c-family](https://github.com/JarvisDing-sdu/yasa-engine/tree/f25a1b68d45777b1594e3db412549c22b96c6732/test/c-family) |
| 结果、计时及验证材料 | [远程实验记录索引](yasa-cpp-extension/results/clang-parser-20261115/README.md) |

早期工具调研和跨语言微型实验保存在本机 `artifacts/clang-hardening-20261115/report-history-before-condensing.md`。本报告集中展示当前结果、转换过程和后续安排。

[dump]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/interface/compiler-dump.ts
[database]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/compilation-database.ts
[selection]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/build-selection.ts
[preprocess]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/compiler-preprocess.ts
[source-map]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/source-map.ts
[unified]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/index.ts
[c-parser]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-C/src/parser.ts
[cpp-parser]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/parser.ts
[linkage]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/handlers/linkage.ts
[handlers]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/handlers/index.ts
[deep-json]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/util/deep-json.ts
[compiler-json]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/compiler-json.ts
[declarations]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/compiler-declarations.ts
[clang-uast]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/clang-uast.ts
[clang-string]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/clang-string.ts
[runner]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/interface/c-family-runner.ts
[builder]: https://github.com/JarvisDing-sdu/yasa-engine/blob/f25a1b68d45777b1594e3db412549c22b96c6732/src/engine/parser/c-family/c-family-ast-builder.ts
