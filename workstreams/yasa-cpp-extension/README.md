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
