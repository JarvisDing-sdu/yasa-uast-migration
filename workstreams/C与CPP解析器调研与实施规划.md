# C/C++ Parser 阶段报告

更新于 2026 年 11 月 21 日。

## 1. 在哪些项目上比了什么

| 对比内容 | 项目与构建范围 | 实测结果 |
| --- | --- | --- |
| Clang 与 Tree-sitter 的 UAST 导出 | libgit2、Mosquitto、libarchive、libuv、libevent、zlib、Jansson、LZ4、libpng，共 795 个 C 编译单元 | 两条路线均导出 795/795。Clang 的语法诊断为 0；Tree-sitter 的诊断集中在 libgit2、libuv 和 libevent |
| Clang→UAST 修复前后复测 | ncnn 的 CPU 静态库 200 个单元、JsonCpp 3 个、spdlog 7 个 | 210/210 导出，语法诊断为 0。ncnn 的 200 个单元中，164 个无转换诊断，36 个仍有语义缺口 |
| YASA 与 CodeGraph 的调用图 | **curl 的 libcurl 静态库**，190 个 C 编译单元。kilo、linenoise 为小项目对照 | libcurl 无宏直接调用函数对上，YASA 精确率 100%、召回率 99.43%，CodeGraph 分别为 99.27%、98.14%。C++ 大项目的调用图对照仍待开展 |

### 两条 Parser 路线的对照

同学固定每个项目的源码和编译数据库，通过正式 `dumpAllAST` 分别导出 Clang 和 Tree-sitter 两套 UAST，核对编译单元、语法诊断、函数定义和调用表达式记录。每行的“单元”均为该项目所选构建目标的规模。[五项目原始统计](yasa-cpp-extension/results/clang-uast-real-project-20261120/five-project-comparison.json) · [其余项目的统计与 libuv 导出清单](yasa-cpp-extension/results/clang-uast-real-project-20261120/)

| 项目 | 单元 | Clang 语法诊断 | Tree-sitter 语法诊断 |
| --- | ---: | ---: | --- |
| libgit2 | 237 | 0 | 817 条，涉及 191 个单元 |
| Mosquitto（broker、客户端和工具） | 197 | 0 | 0 |
| libarchive | 125 | 0 | 0 |
| libuv | 76 | 0 | 10 条，涉及 2 个单元 |
| libevent | 57 | 0 | 10 条，涉及 5 个单元 |
| zlib、Jansson、LZ4、libpng | 37、33、17、16 | 均为 0 | 均为 0 |

即使两条路线都无语法诊断，导出的结构也可能不同。例如 libarchive 两边都记录了 2,697 个函数定义，调用表达式分别为 12,225 和 12,373 个。判断哪条调用边正确，需要另做调用图评测。

**11 月 20 日合入的 C 转换改动。** 同学补齐了原子操作的内存序、GNU 内联汇编的输入操作数、goto 跳转目标、依赖枚举初始化式和数组尾部的隐式初始化。libarchive 和 libevent 的实际构建还暴露了导出入口对编译参数的限制，修复后可直接使用项目编译数据库。libuv 在最终构建中 76/76 导出、0 partial。汇编执行效果和一般 goto 的完整控制流仍有建模空间。[合入记录与验收说明](Clang-AST-UAST改动报告-20261120.md)

**此前的覆盖基线**分两种。配置化双路线对照覆盖 curl、SQLite、JsonCpp、spdlog 共 308 个单元，后两个项目在 Tree-sitter 下分别有 9、185 条语法诊断，Clang 均为 0。11 月 16 日的 Clang 验收另含 ncnn 和 zlib，共 523/523 导出，覆盖 curl 196、SQLite 102、JsonCpp 3、spdlog 7、ncnn 200、zlib 15 个单元。历史逐文件测试还包括 Redis、curl、SQLite 共 2,279 个文件，以及按扩展名选取的 Protobuf 1,214 个文件，后者比较过脚本与官方 dump 的输出。这些范围随构建配置和选材方式变化。[六项目验收记录](yasa-cpp-extension/results/clang-parser-20261115/semantic-round-20261116.json) · [历史逐文件记录](C与CPP初期Parser结果汇总.md)

### 11 月 21 日的 C++ 修复与复测

使用 ncnn 提交 `45b9b45` 的 CPU 静态构建，关闭 Vulkan、OpenMP、运行时 CPU 分派和 AVX。以同一份源码和编译命令逐单元运行官方 `--dumpAST --cAstBackend clang`，再将函数和调用按名称、原始文件和起始行与上轮核对。JsonCpp 和 spdlog 使用各自固定编译数据库运行官方 `--dumpAllAST`。

| 项目 | 本次导出 | 语法诊断 | partial 单元，上轮 → 本轮 | delete 诊断，上轮 → 本轮 |
| --- | ---: | ---: | ---: | ---: |
| ncnn | 200/200 | 0 | 36 → 36 | 72 → 67 |
| JsonCpp | 3/3 | 0 | 3 → 3 | 1 → 1 |
| spdlog | 7/7 | 0 | 7 → 7 | 0 → 0 |

- **引用赋值。** 前一轮补齐了标准库 `vector` 和 `string` 下标的读写位置。ncnn 的赋值位置诊断从 50 降到 0，JsonCpp 从 26 降到 2。正反例验证了写入一个元素后，读取同一元素和相邻元素的区别。
- **对象析构。** 本轮在能证明实际类型的单一非虚继承链上，按派生类、基类、释放内存的顺序生成调用，保留空指针判断和操作数的单次求值。同时处理了 `using` 引入的类型和使用 `std::size_t` 的释放函数签名。ncnn 的 `c_api.cpp`、`datareader.cpp`、`modelbin.cpp` 分别消除了 2、1、2 处诊断。结构核对新增 23 条调用表达式，已有函数与调用记录均保留。
- **验收边界。** `partial` 表示一个编译单元至少还有一项转换诊断，因此局部修复后总单元数可以持平。53 处 `Layer*` 删除中，21 处导出记录已明确标出需要动态类型，另 32 处仍保留为未展开的删除操作。ncnn 还有 274 处对象分配诊断。Engine 的 C-family、C、C++ 联合回归 386 项通过，类型检查通过。小样例用调用图核对析构目标，并用 Clang、GCC 编译运行核对析构顺序和求值次数。[逐项目复测数据](yasa-cpp-extension/results/clang-parser-20261115/destructor-chain-20261121.json)

### 与 CodeGraph 的调用图评测

curl 提交 `b052c835` 的 `libcurl_static` 目标覆盖 **190 个 C 编译单元、154,750 行 C 源码和 199 个头文件**。评分范围限于库内部调用。上文 curl 的 196 单元属于另一份 Parser 导出配置。历史评测用 Clang/libclang 提取当前配置的项目内直接调用，按调用方和被调方的文件、函数名去重；另在 11 个回调点人工审定并冻结 25 条参考边。YASA 运行 Engine 的 `--checkerIds callgraph --dumpAllCG`，CodeGraph v1.6.2 索引同一源码，再分别与参考集核对。

| libcurl 指标 | YASA | CodeGraph |
| --- | ---: | ---: |
| 无宏直接调用精确率（报出的函数对中有多少正确） | 100% | 99.27% |
| 无宏直接调用召回率（参考函数对中找回多少） | 99.43% | 98.14% |
| 含宏直接调用召回率 | 98.82% | 83.01% |
| 精选回调目标召回 | 回调修复前 0/25，修复后 25/25 | 9/25 |

回调修复扩大了候选集合，抽查的 121 个目标中有 72 个正确、40 个错误、9 个待定。现场记录中，YASA 的 C parser 修复版耗时 151.48 秒，进一步修复回调后耗时 160.6 秒；CodeGraph 为 2.80 秒。并发负载与缓存条件有差异，耗时仅供参考。小项目 kilo 和 linenoise 上，两者都找全了各自的 47 和 144 条参考边。11 月 21 日复跑的是 Parser 导出和回归测试，以上调用图数字沿用历史记录。[libcurl 直接调用评测](yasa-c-extension/callgraph-eval/reports/02-curl-comparison.md) · [回调复测](yasa-c-extension/callgraph-eval/reports/03-curl-callback-fix-retest.md) · [误报抽查](yasa-c-extension/callgraph-eval/reports/04-callback-edge-audit.md) · [小项目评测](yasa-c-extension/callgraph-eval/reports/01-small-projects-comparison.md)

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

### 历史 Parser 性能测量

同一源码和编译配置，各运行三次取中位数，包含预处理、转换和导出。

| 样本 | 优化前 | 优化后 | 耗时下降 |
| --- | ---: | ---: | ---: |
| curl altsvc.c | 1.53 秒 | 1.25 秒 | 18.3% |
| curl openssl.c | 3.71 秒 | 2.60 秒 | 29.9% |
| spdlog.cpp | 24.40 秒 | 13.90 秒 | 43.0% |
| async.cpp | 9.98 秒 | 6.10 秒 | 38.9% |

`async.cpp` 的中间 AST JSON 从约 320 MB 减至 117 MB。`spdlog.cpp` 的峰值 RSS 中位数从约 660 MiB 降至 541 MiB，两个 C 样本的峰值 RSS 略有增加。

## 3. 剩余问题与推进顺序

1. 优先追踪工厂函数、参数和容器传出的基类指针，验证虚析构的候选目标。继续用两个派生类、指针重新赋值及空指针作正反例，再复测 ncnn。
2. 按语言特性分别补齐复杂分配、成员析构和模板实例化，复测 ncnn、JsonCpp、spdlog，记录减少的诊断以及受影响的函数和调用。
3. 在固定的 C++ 构建目标上另建调用图参考集，用 Engine 与 CodeGraph 评测直接调用和动态调用，分别记录准召率、超时、耗时和峰值内存。

## 4. 复现入口

在 Engine 工作区运行以下命令，`$unit`、`$db` 分别指向同一构建的源码和编译数据库，`$out` 是新的输出文件。

```bash
node --import tsx src/main.ts --sourcePath "$unit" --language cpp --dumpAST \
  --cCompileCommands "$db" --cAstBackend clang --report "$out"
```

批量导出用 `--dumpAllAST`，将 `--sourcePath` 指向项目源码目录，`--report` 指向新的输出目录。切换 Parser 对照时使用 `--cAstBackend tree-sitter`。调用图评测的命令与构建配置见上面的 libcurl 评测记录。

11 月 21 日复测使用的 Engine 修复已提交到 `codex/cpp-base-semantics` 分支，集成仓库的 `engine` 子模块指向同一版本。[Engine 提交 36d53f3](https://github.com/JarvisDing-sdu/yasa-engine/commit/36d53f3b2e5e0f966ca6150ea58cba0967daebf1)。完整 ncnn 导出、逐文件清单、源码哈希、测试日志和对照程序在本机 `artifacts/clang-session-30min-20261115/ncnn-destructor-chain-nov21/`。下列源码链接固定为历史版本，便于查阅两条路线的实现原理。

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
