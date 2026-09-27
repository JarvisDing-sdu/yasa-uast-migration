# 完整 xAST 检出对比与性能对比

日期：2026-09-12

## 背景

本记录是「后续建议」第 3 点（*在测试基准库上执行完整 Engine 新旧检出与性能对比*）
的落地结果。此前已完成的验证包括：xAST `sast-python3` 的 UAST 正文差分
（800/800 一致）与 no-init-dispatch 小靶场的检出对比（12 文件、7 条）。
但「完整 800 文件的 Engine 检出对比」与「新旧耗时/峰值内存对比」尚未执行，
本文补齐这两项。

## 测试环境

| 项 | 值 |
| --- | --- |
| 机器 | macOS ARM64（Apple Silicon） |
| Node.js | v25.9.0 |
| 旧解析器 oracle | CPython 3.14.5 + 仓库原 Visitor（`legacy.py`） |
| 旧解析器二进制 | 官方 `uast4py-mac-arm64`（v0.2.18） |
| 新解析器 | `tree-sitter-python@0.25.0` + `web-tree-sitter@0.26.8`（WASM） |
| 测试基准 | `alipay/ant-application-security-testing-benchmark` @ `d825758`，`sast-python3`（800 个 .py） |
| 规则 | `engine/test/python/rule_config_xast_python3.json`（`taint_flow_test`，`taint_src → os.system`） |

各仓库固定版本：

- YASA-Engine：`0e69c5f`（`snapshot: YASA-Engine with tree-sitter Python parser`）
- YASA-UAST：`c64cb8a`（`snapshot: YASA-UAST with tree-sitter Python parser`）
- 迁移工作区 main：`840733f`（`feat: migrate Python UAST parser to tree-sitter`）

## 测试方法

1. **改造 runner 支持完整目录**：`tree-sitter-scan-runner.ts` 原实现仅支持
   平铺目录（`no-init-dispatch-cases`），本次为其增加递归遍历与目录参数，
   使其可扫描 `sast-python3` 的四层嵌套结构。改动为向后兼容：不传目录参数时
   行为与原版一致（已用原版/改造版 A/B 逐字对比验证，输出完全一致）。
2. **新旧两条链路**：`new` 模式走 tree-sitter 解析；`legacy` 模式通过
   `PYTHON_UAST_ORACLE` 调用 `legacy.py --batch --unit` 批量解析，
   两条链路共用同一套 Engine 规则分析，仅 UAST 来源不同。
3. **解析可解性摸底**：新旧解析器分别解析全部 800 文件，确定可比集合。
4. **性能测量**：纯解析与完整 Engine 扫描各测 3 次，取中位数。

## 解析可解性

800 个文件，新旧解析器均全部解析成功（0 失败），可比集合为全部 800 文件。
`sast-python3` 样本语法较为基础，未命中新解析器已知的语法缺口
（命名 Unicode 转义、3.14 template string、部分泛型默认值）。

### 本机补充复测：606 文件 UAST 差分（2026-09-13）

本节是对上述 macOS / CPython 3.14.5 结果的独立复测，不能与 800 文件结果混为一谈。
本机使用 Linux（WSL）、Node.js v20.20.0、CPython 3.10.12，以及先前由
`prepare-python-benchmark.ts` 准备的
`engine/test/python/benchmarks/sast-python3/case/`。该目录包含 606 个 Python 文件，
与上文的 800 文件、`d825758` 输入版本不同。

命令如下：

```bash
cd uast/parser-Python
PYTHON_UAST_ORACLE="$PWD/.venv/bin/python" \
  npm run test:compare -- ../../engine/test/python/benchmarks/sast-python3/case
```

`test:compare` 将新 Tree-sitter Visitor 输出的 `body` 与仓库保留的旧 Python Visitor
(`tests/legacy.py`) 逐字段比较；它**不会**删除 `loc` 或 `_meta`，因此位置差也会计入差异。

| 结果 | 文件数 | 含义 |
| --- | ---: | --- |
| 完全一致 | 588 | UAST 所有比较字段一致。 |
| 仅 `loc.column` 不同 | 16 | 语义节点字段、操作符、参数和 `_meta` 一致，仅列号范围不同。 |
| 旧 oracle 无法解析 | 2 | `except*` 异常组语法；本机 CPython 3.10 不支持该 Python 3.11 语法。 |
| 已发现的非位置语义差异 | 0 | 在双方都可解析的 604 个文件中未发现。 |

16 个位置差集中在 `for enumerate/zip` 样例和 f-string/template literal 的字符串片段位置。
例如 Tree-sitter 给出的表达式片段列范围与旧 CPython AST Visitor 的范围不同；这会影响严格的
源码位置回归，但不等价于数据流语义改变。随后使用新 parser 对同一 606 文件执行完整 Engine
`taint_flow_test` 扫描，得到 **332 个 findings**，与该本地旧 parser xAST 基线的 finding
总数相同。该 finding 数一致是补充证据；严格的“逐条 finding / trace 文本一致”仍应在使用
支持 `except*` 的旧 oracle（Python 3.11+）时完成。

## 检出对比结果

| 指标 | new（tree-sitter） | legacy（Python oracle） |
| --- | ---: | ---: |
| 分析文件数 | 800 | 800 |
| Findings | 351 | 351 |
| 完整 findings 文本 | 500075 字符 / 9109 行 | 500075 字符 / 9109 行 |

结论：800 文件的完整 findings **逐字一致**（含每条 trace 的每一步），
`new` 与 `legacy` 的输出无任何差异。tree-sitter 迁移在完整 xAST 检出层
与旧解析器完全对齐，未发现回归。

### 本机 606 文件完整 SARIF / trace 对比（2026-09-14）

本机固定 xAST Python 3 输入为 `engine/test/python/benchmarks/sast-python3/case/`，共 606
个文件。旧基线 SARIF 为 `engine/test/python/report/report.sarif`；新 Tree-sitter parser 使用
相同 `taint_flow_test`、同一 rule config、单 worker 重跑，输出到 Git 忽略目录：

```text
artifacts/xast-python3-new-tree-sitter-taint-regression/
```

新扫描结果：

```text
606 files
332 findings
1,993 marked sources
3,682 matched sinks
1,295 entrypoints
```

比较器：

```text
workstreams/yasa-python-migration/scripts/compare_yasa_sarif.py
```

比较原则是保留 rule、文件、行列、sink、entrypoint 与完整 `codeFlow/threadFlow`，只规范化：

```text
nodeHash：新旧 UAST 节点对象的派生 hash，不是漏洞语义
/case/ → /：旧 binary 在 trace 中使用的历史 xAST source-root 拼写
```

比较结果：

| 指标 | 结果 |
| --- | --- |
| old finding | 332 |
| new finding | 332 |
| finding identity | 完全一致 |
| old-only / new-only finding | 0 / 0 |
| 规范化后完整 SARIF result | 完全一致 |

因此，本机 606 文件的 c 项不仅是“332 对 332”，而是所有 finding 和每条污点链在去除
派生环境字段后完全一致。

## 性能对比

数据均为 3 次运行的中位数。

### 纯解析（800 文件）

| 指标 | 新 tree-sitter | 旧官方二进制 | 对比 |
| --- | ---: | ---: | --- |
| 解析耗时 | 136.8 ms | 12.69 s | 新快约 92 倍 |
| 峰值内存 | 115.8 MiB | 34.7 MiB | 旧省约 3.3 倍 |

口径说明：

- 新解析器耗时 = `corpus.ts` 的读取 + 解析（不写文件），内存 = Node 进程 RSS
  （含 Node 运行时与 WASM）。
- 旧二进制耗时 = 墙钟（含写 800 个 JSON 文件的 I/O），内存 = Python 进程
  peak RSS（含 Python 运行时）。旧二进制的 CPU 时间约 1.75 s，墙钟大头在写文件
  I/O。
- 两者运行时不同（Node vs Python），内存对比含运行时开销，非纯解析器内存。

### 完整 Engine 扫描（800 文件，含规则分析）

| 指标 | new（tree-sitter+Engine） | legacy（Python oracle+Engine） | 对比 |
| --- | ---: | ---: | --- |
| 总耗时 | 2.92 s | 4.26 s | 新快约 31% |
| 峰值内存 | 264.41 MB | 324.78 MB | 新省约 60 MB（18.6%） |
| Findings | 351 | 351 | 一致 |

口径说明：完整扫描的「旧」边是 Python oracle（runner 现有 legacy 实现通过
`legacy.py --batch` 批量解析），非官方二进制。如需官方二进制的完整扫描对比，
需在 runner 中新增调用官方二进制的分支。

## 结论

1. **检出层**：tree-sitter 迁移在完整 800 文件上，检出结果与旧解析器逐字一致，
   无任何回归。
2. **解析层**：新解析器比官方二进制快约 92 倍（墙钟）；若按 CPU 时间计，
   新约 137 ms 对旧约 1.75 s，仍快约 13 倍。进程内存方面新方案更高，
   主要来自 Node 运行时与 WASM 开销。
3. **完整扫描**：新方案比旧方案快约 31%，峰值内存省约 18.6%。

## 复现命令

环境准备（Parser 构建 + 旧解析器 oracle）：

```bash
cd uast/parser-Python
npm ci --ignore-scripts
npm run build
python3.14 -m venv /tmp/yasa-python-oracle
/tmp/yasa-python-oracle/bin/pip install -r requirements.txt

cd ../../engine
npm ci --ignore-scripts
```

下载官方旧二进制（可选，性能对比用）：

```bash
curl -L -o runtime/uast-v0.2.18/uast4py-mac-arm64 \
  https://github.com/antgroup/YASA-UAST/releases/download/v0.2.18/uast4py-mac-arm64
chmod +x runtime/uast-v0.2.18/uast4py-mac-arm64
```

完整检出对比：

```bash
cd engine
node --import tsx test/python/tree-sitter-scan-runner.ts new /path/to/sast-python3
PYTHON_UAST_ORACLE=/tmp/yasa-python-oracle/bin/python \
  node --import tsx test/python/tree-sitter-scan-runner.ts legacy /path/to/sast-python3
```

纯解析性能（新 vs 旧二进制）：

```bash
cd uast/parser-Python
node --import tsx tests/corpus.ts /path/to/sast-python3

/usr/bin/time -l runtime/uast-v0.2.18/uast4py-mac-arm64 \
  --rootDir /path/to/sast-python3 --output /tmp/legacy-uast.json -j 1
```

## 独立复测补充（2026-09-17）

本次在 macOS ARM64、Node.js v25.9.0、CPython 3.11.15 下，对
`main-forYasaTest@32a74f8` 经 Engine 官方准备脚本裁剪后的 606 文件重新测试。上游与本地
文件名及逐文件 SHA-256 完全一致；旧 oracle 对 606 文件全部解析成功。

为防止 legacy 链路遗漏文件后回落到新 parser，本次让旧链路使用与
`PythonAnalyzer.scanModules` 相同的 globby 规则，并监测 `Parser.parseSingleFile` 回落次数。
5 轮 legacy 扫描的回落次数均为 0；主动从 oracle 结果中删除 3 个文件时，扫描因新 parser
未初始化而直接失败，证明不会静默混用两种 parser。

### 检出与 UAST 结果

5 轮独立进程扫描中，新旧两侧每轮均为 606 文件、332 finding。10 份
`findings.result` 只有一个 MD5，10 份原始 `report.sarif` 也只有一个 MD5；无需规范化
`nodeHash` 或路径即可逐字节一致。

解析器层面的逐字段比较仍发现 18 个文件存在差异：

| 结果 | 文件数 |
| --- | ---: |
| UAST 完全一致 | 588 |
| 仅 `loc.start/end.column` 不同 | 18 |
| 非位置差异 | 0 |
| oracle 解析失败 | 0 |

此前 CPython 3.10 复测中的 16 个位置差和 2 个 `except*` 解析失败，在 3.11.15 下变为
18 个位置差。18 个差异文件中有 8 个进入 finding 或 trace，但 SARIF 仍逐字节一致：
差异位于 f-string 文本片段等内部节点，而 trace 使用的是外层调用表达式的位置。

Engine 的 `execInstCount` 稳定相差 2（new 28,784，legacy 28,782），不影响 finding。
因此更精确的表述是：**检出与污点链逐字节一致，但 UAST 和内部执行计数并非完全相同**。

### 本机性能

旧侧使用单批 CPython Visitor oracle，不包含官方二进制的启动、临时 JSON 写入与读取开销。
5 轮中位数如下：

| 指标 | new | legacy | 对比 |
| --- | ---: | ---: | --- |
| 端到端墙钟 | 2,713 ms | 4,020 ms | new 快约 32.5% |
| Engine `parseCode` | 520 ms | 1,825 ms | new 快约 3.51 倍 |
| 峰值 RSS | 556.1 MB | 563.4 MB | 本口径下基本相当 |

峰值 RSS 为整个 Node 进程的 `/usr/bin/time -l` 结果，未计 legacy Python 子进程内存，
因此不能据此评价两个 parser 本身的内存优劣。
