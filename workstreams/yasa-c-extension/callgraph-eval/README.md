# Yasa C 与 CodeGraph：调用图对比评测

对比对象是两个工具输出的**调用图**（哪个函数调用了哪个函数），按准确率和召回率评分；不比较漏洞检测。方法的通俗说明见 [reports/CodeGraph与Yasa对比说明.pdf](reports/CodeGraph与Yasa对比说明.pdf)。

## 报告

| 文件 | 内容 |
| --- | --- |
| [01-small-projects-comparison.md](reports/01-small-projects-comparison.md) | 首轮对比：kilo、linenoise 两个小项目和一组 C 语义样本 |
| [01-small-projects-reproduce.md](reports/01-small-projects-reproduce.md) | 首轮对比的复现步骤 |
| [02-curl-comparison.md](reports/02-curl-comparison.md) | curl（libcurl 静态库完整配置）大项目对比，含 parser 条件编译边界修复前后 |
| [02-curl-protocol.md](reports/02-curl-protocol.md) | curl 对比的评分口径 |
| [03-curl-callback-fix-retest.md](reports/03-curl-callback-fix-retest.md) | 回调解析修复后在 curl 上的复测 |
| [04-callback-edge-audit.md](reports/04-callback-edge-audit.md) | 回调修复新增调用边的精确率审计（clang 类型核对 + 人工抽样） |

报告中“未提交的修复候选”等描述是撰写时的状态。对应的代码已随本次更新提交：

- parser 条件编译边界修复：JarvisDing-sdu/yasa-uast，分支 `fix/c-preprocessor-conditional-boundary`
- 回调解析修复：JarvisDing-sdu/yasa-engine，分支 `fix/c-callback-resolution`

## 结果数据

- `results/small-projects-results.json`：首轮对比的计数与明细。
- `results/curl/`：curl 对比的分数（`results.json`）、错配明细（`mismatches.json`）、Yasa 运行配置，回调修复版的分数和明细（`yasa-callback-*.json`），以及冻结的回调样本（`indirect-gold.json`，11 个调用点 / 25 条目标边）及其说明。
- `results/curl-callback-audit/`：新增回调边的审计数据：clang 独立提取的字段存储（`curl-field-stores.json`）、逐条类型核对（`type-level-check.json`）、固定种子抽样与逐条人工判定（`level2-*.json`）。

## 脚本

`scripts/` 是评测时实际使用的脚本，路径仍按原评测工作区的目录结构编写（例如 `curl-large/`、`callback-fix/`），需要放回对应结构或按需修改路径后运行。

## 与原件的差异

为避免公开本机目录，本目录中文本文件里的本机工作区路径已替换为 `<workspace>`，并对一处措辞做了中性化修改。因此 `results/curl/indirect-gold.json` 与评测时冻结的原件不是逐字节相同：

- 原件 SHA256：`64d8f77f8e0599683012cbf19fa01be3c4aa12b176e2f024373de49e9dcf41e1`（见 `indirect-gold.original.sha256`，分数文件中的 `curated_gold_sha256` 也指原件）
- 本目录副本 SHA256：`ff8f0d14d119fabeb0a1739f383475007c46a968bf31094fb24c1b069eeaa7ca`

逐字节一致的原件、完整的 clang 标准答案（约 28 MB）、CodeGraph 数据库、各工具原始输出和日志在下面的证据包中。证据包内的路径未做替换。

## 证据包（GitHub Release `c-callgraph-eval-2026-11`）

| 文件 | 大小 | SHA256 |
| --- | ---: | --- |
| `Curl-C-callgraph-evidence.zip` | 13.5 MB | `177e9662cab8f178978b69c7c345f7d67fdf8a28a2da2de406ca36e9594b829d` |
| `C-callgraph-reproduction.zip` | 2.1 MB | `47eafe487ed51bf3138bb360392bde769574c5efb4da10d53ed593debbff9e8e` |
| `C-parser-boundary-repro.zip` | 0.8 MB | `eda02f5998b0a41b8151ab7ea8bbacc949cea771ac700ebd831432dcc5111738` |
| `Curl-C-callback-fix-evidence.zip` | 1.6 MB | `d741fc59b5c70efa8af3bda5d4f315c9d9a089b19078b5b100933720b47fd8bd` |
