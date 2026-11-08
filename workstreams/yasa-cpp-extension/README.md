# YASA C++ 支持工作流

目标：让 YASA 用污点分析扫描 C++ 项目，并按 C 扩展的四项验收方式评估；现有 C 支持的行为保持不变。

- 设计：[docs/2026-11-08-cpp-support-design.md](docs/2026-11-08-cpp-support-design.md)
- M0 + M1 实施计划：[docs/2026-11-08-cpp-m0-m1-plan.md](docs/2026-11-08-cpp-m0-m1-plan.md)

## C 回归

`scripts/c_regression.sh OUT [--compare BASE] [--skip juliet,curl]` 检查 C 支持是否保持不变：

| 项 | 内容 |
| --- | --- |
| parser-C 单测 | 无失败，基线中的测试全部通过 |
| Engine `test-c` | 同上（测试文件取自 `engine/package.json` 的 `test-c` 脚本） |
| sast-c | 逐用例结果相同 |
| parser-C UAST 快照 | `scripts/c_uast_snapshot.ts`：语料中每个 `.c` / `.h` 单独解析（Linux 目标，不解析 include），对去掉 `parent` 的 UAST JSON 取 SHA256，逐文件相同 |
| Juliet C | CWE78 / CWE134 × char / wchar_t，`juliet_c.py` 的计分相同 |
| curl 调用图 | `scripts/curl_callgraph_score.py`：与 callgraph-eval 相同的参数和 8 GB 堆，`primary_strict`、`full_ast_direct_pair_recall`、`curated_indirect` 相同 |

UAST 快照语料：sast-c；curl `b052c835`；Redis `ad49ff0d`；SQLite `9626d89e`，共 2,451 个文件。快照连续运行两次结果相同（确定性已核对）。

路径通过环境变量指定，默认值对应原评测工作区：`YASA_ROOT`、`CORPUS`、`JULIET`、`CURL_LARGE`、`NODE_BUNDLE`。

基线：`results/c-baseline/summary.json`，在未改动的代码（engine `8efda87`、uast `36b3cee`）上生成。仓库只保存 summary，原始输出可重新运行脚本生成。

## 使用

```bash
cd engine
npx tsx src/main.ts --sourcePath <项目> --language cpp \
  --ruleConfigFile resource/example-rule-config/rule_config_cpp.json \
  --checkerPackIds taint-flow-cpp-default --report <输出目录>
```

cpp 模式扫描 `.cpp .cc .cxx .c++ .hpp .hh .hxx .h .inl`，`.h` 按 C++ 解析，`.c` 不参与；预处理选项（`--cIncludeDir`、`-D/-U`）与 C 相同，并定义 `__cplusplus=201703L`。

## M1 检查点（2026-11-08）

代码：uast `36b3cee..f2097bd`（parser-C 扩展点、parser-CPP），engine `8efda87..bd15cac`（cpp 语言、CppAnalyzer、`taint_flow_cpp_input`）。

### 特性清单

| 状态 | 特性 |
| --- | --- |
| 已建模 | C 子集（与 C 分析相同）；命名空间（嵌套、`A::B`、匿名）；限定名调用（`A::f`、`std::system`、`::g`）；`using namespace` / `using A::f`（同一编译单元内）；`if/switch/while` 条件中的声明与 init 语句；`nullptr`；`static_cast` 等四种具名转换 |
| 只解析不建模 | 引用 `T&` / `T&&`（UAST 上有 `_meta.reference`，Engine 仍按值处理）；类与成员函数（类外定义的限定符按命名空间处理）；模板（解析失败的部分由 tree-sitter 错误恢复跳过） |
| 不支持 | `new` / `delete` 表达式；虚函数分派；STL 容器与 iostream 模型；异常；lambda；头文件中的 `using` 作用到包含者 |

### Juliet C++

`scripts/juliet_cpp.py`（计分口径同 `juliet_c.py`）。CWE78 / CWE134 的 C++ 用例没有 01 号变体（只有 33、43、62、72–74、81–84 这些 C++ 特有变体），因此跑全部 C++ 用例；CWE23 / CWE36 跑 01 号变体。结果在 `results/m1/juliet/`。

| 集合 | 用例 | TP | FN | TN | FP |
| --- | --- | --- | --- | --- | --- |
| CWE78 char（全部 C++ 变体） | 500 | 80 | 420 | 500 | 0 |
| CWE78 wchar_t（全部 C++ 变体） | 500 | 80 | 420 | 500 | 0 |
| CWE134 char（全部 C++ 变体） | 300 | 48 | 252 | 300 | 0 |
| CWE134 wchar_t（全部 C++ 变体） | 300 | 48 | 252 | 300 | 0 |
| CWE23 char / wchar_t（01） | 25 / 25 | 10 / 10 | 15 / 15 | 25 / 25 | 0 / 0 |
| CWE36 char / wchar_t（01） | 25 / 25 | 10 / 10 | 15 / 15 | 25 / 25 | 0 / 0 |

漏报按原因分类（CWE78 / CWE134 两种字符类型相同）：

| 原因 | 涉及 | 归属 |
| --- | --- | --- |
| 类与虚函数 | 81–84 号变体全部 | M2 |
| 引用别名（`char *&dataRef = data` 先于赋值绑定） | 33 号变体全部 | M2 |
| STL 容器传递数据 | 72–74 号变体全部 | M3 |
| C++ 文件流 `ifstream` / `ofstream` | CWE23/36 01 号的这两个 sink | M3 |
| 规则缺失：`CreateFile` | CWE23/36 01 号的 w32CreateFile sink | 规则补充 |
| 被调函数中 `strncat(data+len, getenv(...))` 写入参数指向的缓冲区 | 43/62 号的 environment source | C 引擎已有局限（同样的 C 代码也漏报），不是 C++ 引入 |

43 / 62 号变体中其余 source 全部检出；所有集合误报为 0。

### C 回归

`results/m1/c-regression/summary.json`：与基线完全一致（parser-C、test-c、sast-c、2,451 个文件的 UAST 快照、Juliet C、curl 调用图）。


## M1 评审修复（2026-11-08）

修复说明：[docs/2026-11-08-cpp-m1-review-fixes.md](docs/2026-11-08-cpp-m1-review-fixes.md)。Engine `d677345`、UAST `73bb510`；已合入各自最新 main，并保留 C 编译单元控制流修复。

本轮处理名称查找、命名空间外定义、using 的函数/块范围、变量统一读写绑定、匿名命名空间内部链接、用户标准库同名函数、条件函数定义并集、while 条件声明重复求值及其初始化器；补充原始字符串。C++ 测试 40 项、parser-CPP 18 项通过。混合项目测试现在要求 .h 中的实现实际参与分析。

Juliet C++ 重测的 8 份评分 JSON 与原 M1 完全相同（包括逐用例结果），没有总体召回率提升。新结果见 [results/m1-review-fixes](results/m1-review-fixes)，旧 `results/c-baseline` 和 `results/m1` 保留。

`scripts/juliet_cpp.py` 先校验 run.json、批次退出状态、源文件清单与哈希、扫描摘要/文件数、SARIF 数量和 unmapped；不完整结果拒绝计分。零发现的成功扫描允许没有 SARIF，原始结果归档后可重计分。新运行必须使用空输出目录；旧版无完整运行清单的输出不会被新版脚本直接当作有效证据。完整性测试 13 项与自测通过。

剩余范围仍包括类/虚函数、引用别名、STL 与文件流、包含者的 header using 等。本次额外发现动态全局初始化中的 source 未检出，已在修复说明中记录，未算作支持完成。

完整 C 回归比较通过：C 原测试均保留且零失败，sast-c 逐用例、2,451 个 UAST 快照、四组 Juliet C 评分和 curl 三块调用图评分与原基线逐项一致。详细核验见 `results/m1-review-fixes/verification.json`。
