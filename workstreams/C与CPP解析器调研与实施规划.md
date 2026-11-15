# C/C++ Parser 阶段报告

更新于 2026 年 11 月 15 日。

## 1. 当前结果

**已跑通真实构建配置下的源码到 UAST 导出，并完成一轮语义修复和性能优化。当前仍处于实验验收阶段。**

| 验证范围 | 当前结果 |
| --- | --- |
| libcurl_static，196 个编译单元 | 全部导出，失败 0，语法诊断 0。96 个单元未触发已知转换缺口，100 个标记为 partial |
| spdlog 静态库，7 个编译单元 | 全部导出，失败 0，语法诊断 0。7 个均标记为 partial |
| 函数定义存在性 | curl 匹配 12,885/12,885 条参考记录，spdlog 匹配 5,157/5,170 条 |
| 回归测试 | parser-C 103 项、parser-CPP 51 项、Engine 联合回归 310 项通过。补充边界及捕获写回测试通过 |
| 冻结混合语言样例 | 13 个阳性、13 个安全对照全部符合预期，1 个预期失败符合要求 |
| 完整 spdlog Engine 分析 | 已完成解析和符号索引，符号解释触发入口预算及整体 600 秒超时，完整分析尚未完成 |

本轮使用 Linux、Clang 21.1.8 和两个静态库目标的编译数据库。curl 配置关闭了 libpsl。`partial` 表示存在尚未完整转换的语义，具体类别保存在逐单元 manifest 中。

函数定义匹配按文件、规范化名称和定义范围核验，包含头文件在不同编译单元中的重复记录。spdlog 余下 13 条匹配差异已定位为声明起始行差异和参考实体重复。调用图准召率仍需单独评分。

## 2. 实现与改进

### 路线一，编译器预处理＋Tree-sitter visitor

以下步骤对应 `--cCompileCommands … --cAstBackend tree-sitter`。每个编译单元独立处理，C/C++ 由 `--language c` 或 `--language cpp` 指定。

| 步骤 | 处理代码 | 输入与处理 | 得到的结果 |
| --- | --- | --- | --- |
| 1. 选择编译配置 | [compiler-dump.ts][dump]、[compilation-database.ts][database]、[build-selection.ts][selection] | 读取源码路径和 `compile_commands.json`，选择对应命令，提取语言、标准、宏及头文件路径 | 当前编译单元的构建上下文，含 `entryId` 与编译参数 |
| 2. 编译器预处理 | [compiler-dump.ts][dump] 调用 [compiler-preprocess.ts][preprocess] 的参数整理逻辑 | 将源码与所选参数交给 Clang/GCC 的 `-E`，展开宏、选择条件分支、展开 include | 编译器标准输出中的预处理文本，暂存在内存 |
| 3. 整理待解析文本 | [source-map.ts][source-map] 的 `decodeLineMarkers`、`projectText` | 读取预处理文本中的行标记，建立源文件映射，将行标记和系统头内容替换为空白，保留项目头文件 | 供 parser 读取的文本及 `sourceMap`，保留预处理后的行位置 |
| 4. 按语言生成语法树 | [parser-CPP/src/index.ts][unified] 分发到 [parser-C/src/parser.ts][c-parser] 或 [parser-CPP/src/parser.ts][cpp-parser] | `parsePreprocessed` 接收上述文本。C 加载 `grammar/tree-sitter-c.wasm`，C++ 加载依赖包中的 `tree-sitter-cpp.wasm`，调用 Tree-sitter 解析 | Tree-sitter 语法树及语法错误位置 |
| 5. visitor 转换 | C 使用 [parser-C/src/parser.ts][c-parser] 的 `visit`。C++ 通过 [handlers/linkage.ts][linkage]、[handlers/index.ts][handlers] 接入声明、表达式、命名空间及语句 handlers，并复用 C 的公共 visitor | 遍历语法节点，将函数、变量、调用和控制流映射为 UAST 节点 | 根节点为 `CompileUnit` 的 UAST，附带 `parseErrors` 等诊断 |
| 6. 导出 | [compiler-dump.ts][dump]、[deep-json.ts][deep-json] | 为 UAST 补充原始文件起始行、编译配置与状态，序列化 JSON | 单文件输出到 `--report` 指定文件。批量输出为 `<entryId>.json` 和 `manifest.json` |

WASM 文件提供 C/C++ 语法规则，TypeScript visitor 负责生成 UAST。这条配置化路径使用 `parsePreprocessed`。普通 `parse()` 入口中的本地宏处理由 `parser-C/src/macros.ts` 承担。

### 路线二，Clang AST＋UAST 适配器

以下步骤对应 `--cCompileCommands … --cAstBackend clang`，编译数据库中的命令需要使用 Clang。C 与 C++ 共用适配器，通过语言模式区分。

| 步骤 | 处理代码 | 输入与处理 | 得到的结果 |
| --- | --- | --- | --- |
| 1. 选择编译配置 | [compiler-dump.ts][dump]、[compilation-database.ts][database]、[build-selection.ts][selection] | 读取源码路径和编译数据库，选定当前单元的 Clang 命令与语言模式 | 构建上下文，含宏、头文件路径、语言标准和 `entryId` |
| 2. 生成预处理文件 | [compiler-preprocess.ts][preprocess] 的 `preprocessUnit`、[source-map.ts][source-map] | 执行依赖检查和 Clang `-E`，展开宏、条件分支及头文件，并记录行标记映射 | 临时目录中的 C `unit.i` 或 C++ `unit.ii`，以及依赖、源码映射记录 |
| 3. 生成编译器 AST | [compiler-preprocess.ts][preprocess] 的 `readDeclarationMetadata`、[compiler-json.ts][compiler-json] | Clang 读取 `.i/.ii`，执行 `-fsyntax-only -Xclang -ast-dump=json`。输出流在落盘时压缩格式空白 | 临时文件 `compiler-ast.json`，包含 Clang 的声明、引用、类型及函数体节点 |
| 4. 读取并选择节点 | [compiler-declarations.ts][declarations] 的 `readCompilerDeclarations` | 严格校验并流式读取 AST JSON，提取声明和引用，按源位置向转换器交付项目声明子树 | 声明元数据与项目 AST 子树，元数据保存为 `declarations.json` |
| 5. 适配为 UAST | [clang-uast.ts][clang-uast] 的 `ClangUastConverter.add/visit/finish`，字符串解码使用 [clang-string.ts][clang-string] | 将 Clang 节点映射为 UAST，恢复默认实参、归属类和源码位置，记录尚未覆盖的语义 | `CompileUnit` UAST，附带 `clangBackend.unsupported` 和转换状态 |
| 6. 导出 | [compiler-dump.ts][dump]、[deep-json.ts][deep-json] | 补充导出元数据并序列化 UAST | 单文件 UAST JSON，或批量 `<entryId>.json` 与 `manifest.json` |

配置化 dump 的第 4、5 步在同一遍流式读取中完成。`.i/.ii` 和编译器 AST 位于临时目录，单次 dump 结束后自动清理。最终保留 UAST JSON 与批量 manifest。

### UAST 怎样交给 Engine

`dumpAST/dumpAllAST` 完成解析和导出。调用图及污点分析通过 [c-family-runner.ts][runner] 的分析入口运行，使用 `--astBackend tree-sitter` 或 `--astBackend clang`。

Engine 分析先读取声明元数据、选取所需的系统包装函数，再由 [c-family-ast-builder.ts][builder] 调用对应 parser 或 `convertClangAstFile`，绑定编译器符号并调用 `processParsedAst`，得到供现有 C-family 分析器消费的 UAST。Clang 分析路径因此保留单独的转换遍历。

两条路线都通过行标记记录原始文件起始行，宏展开后的原始列号标记为未知。当前统一门面位于 `parser-CPP` 包，内部继续依赖 `parser-C`。

### 本轮解决的问题

- **调用与控制流**。恢复项目函数、方法和构造函数的默认实参及字段默认初始化，验证显式实参覆盖、简单 lambda 引用捕获读写和前向 goto。
- **结构与数据保留**。修复类外定义归属、模板构造函数遗漏、透明包装丢弃 throw，以及字符串、宽字符数字表的转换。curl 的空汇编得到明确表示，实际指令和 clobber 继续保留诊断。
- **跨单元符号**。区分模板声明与实例化，识别隐式 inline。正文一致的合法重复定义可合并，冲突正文和普通重复定义仍被拒绝。
- **数据处理**。配置化 dump 将声明提取与项目节点转换合为一次遍历，编译器 JSON 在落盘时流式压缩格式空白。真实样本优化前后的 metadata 和 UAST 校验一致。

### 性能变化

同一源码和编译配置，各运行三次取中位数，包含预处理、转换和导出。

| 样本 | 优化前 | 当前 | 耗时下降 |
| --- | ---: | ---: | ---: |
| curl altsvc.c | 1.53 秒 | 1.25 秒 | 18.3% |
| curl openssl.c | 3.71 秒 | 2.60 秒 | 29.9% |
| spdlog.cpp | 24.40 秒 | 13.90 秒 | 43.0% |
| async.cpp | 9.98 秒 | 6.10 秒 | 38.9% |

`async.cpp` 的中间 AST JSON 从约 320 MB 减至 117 MB。`spdlog.cpp` 的峰值 RSS 中位数从约 660 MiB 降至 541 MiB，两个 C 样本的峰值 RSS 略有增加。

## 3. 剩余问题与推进顺序

**当前继续优先处理 Parser 转换质量和数据处理成本。** 每项修复先用最小样例验证，再复测原问题文件，最后运行完整构建目标。

| 顺序 | 工作重点 | 验收方式 |
| --- | --- | --- |
| 1 | 清理 C 的枚举常量求值、可变实参、复合字面量、GNU statement expression 和后向跳转缺口 | 补充预期 UAST 单测，复测 curl 196 个单元，记录 partial 的数量及原因变化 |
| 2 | 补齐 C++ 剩余默认实参绑定、值捕获和依赖模板名等调用相关语义 | 最小结构及调用样例通过，复测 spdlog 7 个单元，逐项核对转换诊断 |
| 随上述两步复测 | 按实测瓶颈继续优化 Parser 性能 | 检查输出等价性，重复测量耗时和峰值内存 |
| 随后 | 单独定位完整 Engine 的符号解释超时 | 缩减超时入口，完成固定构建目标的分析并保留执行状态 |
| 最后 | 使用正式调用图入口比较 CodeGraph，收敛默认后端与发布包 | 冻结参考集，分别报告准召率、时间和内存，完成统一入口验收 |

多配置结果合并和扩大项目范围放到当前构建目标稳定之后。宏开关先用配对小样例验证，保留各配置身份。

## 4. 代码、命令与实验材料

实现位于独立工作区 `/home/jarvis/文档/projects/yasa-c-family-experiment/`，分支为 `codex/c-family-pilot-20261115`，对应源码、报告和子模块指针随本次提交发布，远程版本见下方链接。

| 查阅内容 | 入口 |
| --- | --- |
| Clang AST→UAST 转换 | [clang-uast.ts][clang-uast] |
| 预处理、AST 读取和符号处理 | [Engine C-family 源码目录](https://github.com/JarvisDing-sdu/yasa-engine/tree/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family) |
| dump 与分析命令说明 | [Engine C-family 文档](https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/docs/c-family.md) |
| 最小样例和集成测试 | [test/c-family](https://github.com/JarvisDing-sdu/yasa-engine/tree/0e79be49652ded000dc124384ca5b672b39f9af4/test/c-family) |
| 结果、计时及验证材料 | [远程实验记录索引](yasa-cpp-extension/results/clang-parser-20261115/README.md) |

早期工具调研和跨语言微型实验保存在本机 `artifacts/clang-hardening-20261115/report-history-before-condensing.md`。本报告集中展示当前结果、转换过程和后续安排。

[dump]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/interface/compiler-dump.ts
[database]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/compilation-database.ts
[selection]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/build-selection.ts
[preprocess]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/compiler-preprocess.ts
[source-map]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/source-map.ts
[unified]: https://github.com/JarvisDing-sdu/yasa-uast/blob/2242701664c04ee7a8013a23d0e2450e5286852c/parser-CPP/src/index.ts
[c-parser]: https://github.com/JarvisDing-sdu/yasa-uast/blob/2242701664c04ee7a8013a23d0e2450e5286852c/parser-C/src/parser.ts
[cpp-parser]: https://github.com/JarvisDing-sdu/yasa-uast/blob/2242701664c04ee7a8013a23d0e2450e5286852c/parser-CPP/src/parser.ts
[linkage]: https://github.com/JarvisDing-sdu/yasa-uast/blob/2242701664c04ee7a8013a23d0e2450e5286852c/parser-CPP/src/handlers/linkage.ts
[handlers]: https://github.com/JarvisDing-sdu/yasa-uast/blob/2242701664c04ee7a8013a23d0e2450e5286852c/parser-CPP/src/handlers/index.ts
[deep-json]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/util/deep-json.ts
[compiler-json]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/compiler-json.ts
[declarations]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/compiler-declarations.ts
[clang-uast]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/clang-uast.ts
[clang-string]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/clang-string.ts
[runner]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/interface/c-family-runner.ts
[builder]: https://github.com/JarvisDing-sdu/yasa-engine/blob/0e79be49652ded000dc124384ca5b672b39f9af4/src/engine/parser/c-family/c-family-ast-builder.ts
