# C/C++ Parser 阶段报告

更新于 2026 年 11 月 16 日。

## 1. 当前结果

**已跑通真实构建配置下的源码到 UAST 导出，并完成一轮语义修复和性能优化。当前仍处于实验验收阶段。**

| 验证范围 | 当前结果 |
| --- | --- |
| libcurl_static，196 个编译单元 | 全部导出，失败 0，语法诊断 0。180 个单元未触发已知转换缺口，16 个标记为 partial。196 个根节点均为 `CompileUnit` |
| spdlog 静态库，7 个编译单元 | 全部导出，失败 0，语法诊断 0。7 个均标记为 partial |
| 函数定义存在性，既有参考核验 | curl 匹配 12,885/12,885 条参考记录，spdlog 匹配 5,157/5,170 条 |
| 回归测试 | 独立 parser 单测上轮为 C 103 项、C++ 51 项。最新联合回归 343 项检查通过，原有 2 项缺口复现已转为正常功能检查。parser-CPP 最新 54 项单测通过，TypeScript 检查通过 |
| 冻结混合语言样例 | 13 个阳性、13 个安全对照全部符合预期，1 个预期失败符合要求 |
| 完整 spdlog Engine 分析 | 已完成解析和符号索引，符号解释触发入口预算及整体 600 秒超时，完整分析尚未完成 |

验证使用 Linux、Clang 21.1.8 和各项目所选构建目标的编译数据库。此前完整目标复测覆盖 curl、SQLite、spdlog、jsoncpp 的两条路线；本次修复后重跑了这四个项目的 Clang 路线。curl 配置关闭了 libpsl。`partial` 表示存在尚未完整转换的语义，具体类别保存在逐单元 manifest 中。

函数定义匹配按文件、规范化名称和定义范围核验，包含头文件在不同编译单元中的重复记录。spdlog 余下 13 条匹配差异已定位为声明起始行差异和参考实体重复。调用图准召率仍需单独评分。

### 跨项目验收与语言覆盖

固定项目验收统一调用正式 `dumpAllAST`，冻结源码文件校验值、编译数据库、后端及转换代码，导出后核对覆盖数、根节点、函数记录、语法诊断和未转换节点。SQLite 和 jsoncpp 均按所选配置实际构建静态库，两条解析路线复用对应编译数据库。最新结果见 [固定项目验收记录](yasa-cpp-extension/results/clang-parser-20261115/fixed-projects-validation.json)，首次基线保留在 [交叉验收记录](yasa-cpp-extension/results/clang-parser-20261115/cross-project-validation.json)。本轮覆盖 308 个选定编译单元，两条路线合计 616 次导出全部成功，运行前后的源码、配置及实现校验一致。

| 项目与角色 | Tree-sitter 路线 | Clang 路线 |
| --- | --- | --- |
| curl，开发样本，196 个单元 | 全部导出，语法诊断 0，114 处泛型表达式未转换 | 全部导出，语法诊断 0，180 个无已知转换缺口，16 个 partial |
| SQLite，历史回归，102 个单元 | 全部导出，语法诊断 0，6 处泛型表达式未转换 | 全部导出，语法诊断 0，83 个无已知转换缺口、19 个 partial |
| jsoncpp，独立基线后转回归，3 个单元 | 全部导出，9 条语法诊断，恢复 3 个 lambda 函数体 | 全部导出，语法诊断 0，3 个均为 partial |
| spdlog，历史回归，7 个单元 | 全部导出，185 条语法诊断，并有模板、捕获等转换缺口 | 全部导出，语法诊断 0，7 个均为 partial |

新增独立项目基线使用 zlib 静态库和 ncnn CPU 静态库，均按自己的构建系统成功编译。zlib 的 15 个单元全部导出、语法诊断 0，14 个无已知转换缺口，1 个因后向 goto 标为 partial。ncnn 配置关闭 Vulkan、OpenMP、运行时 CPU 分派和 AVX，200 个单元全部导出、语法诊断 0，其中 8 个无已知转换缺口，192 个 partial。ncnn 首次遇到 dump 参数限制的 200 条失败记录已保留，参数修复后的完整基线用于后续结构回归。宏、生成头文件及跨文件信息的保留继续通过真实构建目标验收。

本次 30 分钟修复后的 Clang 路线复测覆盖上述四个固定项目的全部 308 个编译单元，以及 ncnn 的 5 个问题单元，全部导出、语法诊断 0。按原始位置核对调用表达式记录，jsoncpp 从 2,251 增至 2,277，spdlog 从 17,740 增至 17,988，ncnn 的 5 个单元从 1,985 增至 2,006；curl、SQLite 数量不变，各组均未发现旧调用记录丢失。记录可能包含头文件在多个单元中的重复项，不能用这些数字替代调用图准召率。ncnn 全部 200 个单元的最终版复测已于 11 月 16 日完成，结果如下。详见 [本次结果与命令](yasa-cpp-extension/results/clang-parser-20261115/clang-session-30min-summary.json)。

SQLite 两条路线各导出 2,744 条函数定义记录，函数数量用于结构检查。jsoncpp 首次验收结果已冻结，后续纳入回归项目。Redis 保留历史回归身份，本轮未重跑。各路线的诊断类别不同，当前结果用于定位缺口，调用图评分另行进行。

| 语言能力 | 已有及新增验收 | 当前边界 |
| --- | --- | --- |
| 宏、条件分支、项目头文件 | C/C++、开关各两种取值，双路线检查调用目标和原始文件行号 | 多配置合并待做 |
| typedef、函数指针、多维数组 | 双路线声明、数组层级及调用结构检查 | 复杂声明组合继续补充 |
| 分支、循环、switch、嵌套作用域 | 双路线结构检查，Clang 另有作用域和赋值传播回归 | 后向 goto 等缺口已记录 |
| 指定初始化、复合字面量 | 双路线按字段名和值核对，Clang 另有输入传播对照 | 隐式数组尾部补零仍有缺口 |
| 枚举、变参、字符串及宽字符 | 现有 Clang 边界测试覆盖取值、类型和编码 | 超范围整数转换保留诊断 |
| C++ 重载、构造函数 | 双路线检查重载结构，Clang 检查构造标记和初始化 | 构造函数定义标记已补齐，初始化列表语义继续保留诊断 |
| C++ 模板、lambda | 双路线对照；Clang 另有模板、捕获读写回归 | 两路线均保留 lambda 函数体，Tree-sitter 捕获语义继续保留诊断 |
| 成员指针、未知节点与失败 | 最小样例检查操作数和调用保留，缺失语义显式诊断；批量失败测试检查后续单元 | 成员指针目标解析待做 |

`test/c-family/test-parser-feature-matrix.ts` 现有 18 项结构契约检查。此前两项缺口已修复并转为正常功能检查。双路线按字段名核对指定初始化，允许各自保留源码顺序或字段布局顺序。

### 11 月 16 日：原子操作与 C++ 语句表达式修复

**已恢复两类节点的结构；完整复测 508 个编译单元，全部导出成功、语法诊断 0。** 范围为 ncnn 200、curl 196、SQLite 102、jsoncpp 3、spdlog 7 个单元，使用正式 `dumpAST` / `dumpAllAST` 的 Clang 后端。本轮没有新增 Engine 分析语义。

| 修复 | 具体做法 | 真实项目结果与边界 |
| --- | --- | --- |
| 原子操作 `AtomicExpr` | 转为带内建操作名的调用节点；按预处理文本中的参数位置恢复源码参数顺序，保留地址、值和内存序。标明 fetch-add 等操作返回修改前还是修改后的值；位置不足时保留操作数并显式诊断 | ncnn 恢复 570 条记录，来自 `mat.h:1549、1578、1583` 的 3 处源码；curl 恢复 9 条、SQLite 恢复 38 条。原子写回及并发内存序分析仍标记为 partial |
| C++ GNU 语句表达式 `StmtExpr` | 复用已有的带作用域标记的 `Sequence`，保留内部声明、嵌套结构、副作用和末项结果，增加结果类型元数据 | ncnn 的 `cpu.cpp:2371、2376、2386` 三处 `CPU_SET/CLR/ISSET` 展开结构已恢复。C++ 对象清理及临时对象生命周期仍明确诊断 |

- **单测**：修复前 3 个真实编译反例失败，修复后通过；加上参数位置缺失的保留测试，共新增 4 项。联合回归 **343 项通过**，`npm run typecheck` 通过。测试覆盖 C/C++、C11 原子内建操作、比较交换参数顺序、宏定位、嵌套作用域、无返回值语句块和带析构对象。
- **结构核对**：ncnn 调用表达式记录 92,409 → **92,988（+579）**，其中 570 条为原子内建操作，9 条为恢复的语句块中的 `sizeof` 表示；这些不是新增的普通项目函数调用，不能据此声称调用图召回率提升。函数定义保持 26,767 条。五个项目按名称、原始文件和起始行核对，旧调用和函数记录均未丢失。
- **仍有缺口**：ncnn 整节点未转换的位置从 8 处降至 **2 处内联汇编**（`cpu.cpp:569、585`）。仍有 192 个单元为 partial，因为原子内存语义、C++ 生命周期、继承、模板枚举及引用赋值写回等限制没有被隐藏。
- **验收范围**：保持同一 CPU 静态库配置，运行期间源码、配置及实现校验一致；未覆盖 Vulkan、OpenMP、AVX 等其他配置。源码位置另做了文件存在性和行号范围检查，不代表所有位置都已人工核准。

本轮实现见 [clang-uast.ts](https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/clang-uast.ts)，测试位于 [test-clang-uast.ts](https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/test/c-family/test-clang-uast.ts)，已提交到 `codex/c-family-pilot-20261115` 分支。[本轮机器可读结果](yasa-cpp-extension/results/clang-parser-20261115/atomic-stmtexpr-fix-20261116.json)包含测试、源码校验、命令与输出位置；[修复前完整基线](yasa-cpp-extension/results/clang-parser-20261115/ncnn-final-full-20261116.json)继续保留。

下一步可以处理剩余内联汇编的操作数保留，并按最小语言样例完善引用赋值、模板和继承的语义契约；暂不以减少 partial 数量作为唯一目标。

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

**当前按语言特性测试和固定项目基线推进 Parser 转换质量及数据处理成本。** 每项修复先用最小样例验证，再复测原问题文件，最后运行完整构建目标。

| 顺序 | 工作重点 | 验收方式 |
| --- | --- | --- |
| 1 | 处理 C 剩余后向跳转、数组隐式补零和 switch 标签前语句缺口；原子操作的结构已恢复，内存语义另行处理 | 补充预期 UAST 单测，复测 curl 196 个单元，记录 partial 的数量及原因变化 |
| 2 | 补齐 C++ 剩余默认实参绑定、值捕获和依赖模板名等调用相关语义 | 最小结构及调用样例通过，复测 spdlog 7 个单元，逐项核对转换诊断 |
| 随上述两步复测 | 按实测瓶颈继续优化 Parser 性能 | 检查输出等价性，重复测量耗时和峰值内存 |
| 随后 | 单独定位完整 Engine 的符号解释超时 | 缩减超时入口，完成固定构建目标的分析并保留执行状态 |
| 最后 | 使用正式调用图入口比较 CodeGraph，收敛默认后端与发布包 | 冻结参考集，分别报告准召率、时间和内存，完成统一入口验收 |

每个修复先明确语言规则并补最小反例，再运行相关特性与固定项目回归。新增验收项目先冻结首次结果；用于调试后转为回归项目。多配置结果合并随后推进。

## 4. 代码、命令与实验材料

本轮完整结果及校验后的逐单元输出归档位于本机 `artifacts/parser-validation-20261115/final-fixed-projects/`。

跨项目入口为 `workstreams/yasa-cpp-extension/scripts/parser_acceptance.py`，以 `--config 项目配置.json --engine 实验Engine目录 --out 新结果目录` 运行。本轮实际配置及输入锁位于本机 `artifacts/parser-validation-20261115/`，初次导出保存在校验过的 `baseline-exports.tar.gz`。

实现位于独立工作区 `/home/jarvis/文档/projects/yasa-c-family-experiment/`，分支为 `codex/c-family-pilot-20261115`。本轮 C/C++ 修复已提交，下面的远程源码链接固定到本次提交版本。完整 UAST、逐文件日志及源码快照保留在本机，远程仓库保存报告、结果摘要和通用验收脚本。本轮命令、前后结果、测试数量及源码校验值见 [C 验证记录](yasa-cpp-extension/results/clang-parser-20261115/c-hardening-summary.json)，完整逐单元输出位于本机 `artifacts/c-parser-hardening-20261115/curl-verified/`。

| 查阅内容 | 入口 |
| --- | --- |
| Clang AST→UAST 转换 | [clang-uast.ts][clang-uast] |
| 预处理、AST 读取和符号处理 | [Engine C-family 源码目录](https://github.com/JarvisDing-sdu/yasa-engine/tree/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family) |
| dump 与分析命令说明 | [Engine C-family 文档](https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/docs/c-family.md) |
| 最小样例和集成测试 | [test/c-family](https://github.com/JarvisDing-sdu/yasa-engine/tree/fefff259f4bb7d724c849a46fdc39b7380625675/test/c-family) |
| 结果、计时及验证材料 | [远程实验记录索引](yasa-cpp-extension/results/clang-parser-20261115/README.md) |

早期工具调研和跨语言微型实验保存在本机 `artifacts/clang-hardening-20261115/report-history-before-condensing.md`。本报告集中展示当前结果、转换过程和后续安排。

[dump]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/interface/compiler-dump.ts
[database]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/compilation-database.ts
[selection]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/build-selection.ts
[preprocess]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/compiler-preprocess.ts
[source-map]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/source-map.ts
[unified]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/index.ts
[c-parser]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-C/src/parser.ts
[cpp-parser]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/parser.ts
[linkage]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/handlers/linkage.ts
[handlers]: https://github.com/JarvisDing-sdu/yasa-uast/blob/c51763aed6d67b2f3cf965ca0d8c35d4fb0abd66/parser-CPP/src/handlers/index.ts
[deep-json]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/util/deep-json.ts
[compiler-json]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/compiler-json.ts
[declarations]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/compiler-declarations.ts
[clang-uast]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/clang-uast.ts
[clang-string]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/clang-string.ts
[runner]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/interface/c-family-runner.ts
[builder]: https://github.com/JarvisDing-sdu/yasa-engine/blob/fefff259f4bb7d724c849a46fdc39b7380625675/src/engine/parser/c-family/c-family-ast-builder.ts
