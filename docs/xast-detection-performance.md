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

## 检出对比结果

| 指标 | new（tree-sitter） | legacy（Python oracle） |
| --- | ---: | ---: |
| 分析文件数 | 800 | 800 |
| Findings | 351 | 351 |
| 完整 findings 文本 | 500075 字符 / 9109 行 | 500075 字符 / 9109 行 |

结论：800 文件的完整 findings **逐字一致**（含每条 trace 的每一步），
`new` 与 `legacy` 的输出无任何差异。tree-sitter 迁移在完整 xAST 检出层
与旧解析器完全对齐，未发现回归。

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
