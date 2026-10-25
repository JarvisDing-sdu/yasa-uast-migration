# YASA C 语言扩展工作流

目标：让 YASA 支持 C 语言的污点分析，并按 Python 迁移的验收方式（单测、靶场语义流通、大项目解析、真实靶场命中率）评估质量。

```text
C 源码 → uast/parser-C（tree-sitter-c + visitor + 宏展开）→ UAST
       → engine CAnalyzer → taint_flow_c_input → SARIF
```

本实现以之前的 C 原型（`sijie52/parser-c`，只有 parser，Engine 部分未入库）为起点：parser 在原型上修复和扩展，Engine 部分重新实现。

## 目录

- `docs/C扩展-设计与实现.md`：架构、相对原型修复的缺陷、Engine 语义、规则与已知局限；
- `docs/C扩展-四项验收报告.md`：四项验收的数据、命令、固定版本与误报漏报分析；
- `benchmark/`：自建的 xAST 风格 C 靶场 `sast-c`（82 个用例）及其规则；
- `results/`：最终一次验收运行的结果摘要（sast-c、Juliet、CASTLE、大项目解析）；
- `patches/`：两个组件仓库的提交补丁及应用方法（本会话无组件仓库推送权限）；
- `scripts/`：
  - `score_c_benchmark.py`：对 `sast-c` 打分；
  - `juliet_c.py`：在 NIST Juliet C 用例上分批运行并按 bad/good 函数打分；
  - `castle_c.py`：在 CASTLE 上逐文件运行并打分；
  - `c_corpus_parse.ts`：大项目解析覆盖率统计与 UAST dump。

核心代码在子模块中：

- `uast/parser-C/`：C parser 及单测（50 个）；
- `engine/src/engine/parser/c/`、`engine/src/engine/analyzer/c/`、`engine/src/checker/taint/c/`：Engine 接入、分析器与 checker；
- `engine/resource/example-rule-config/rule_config_c.json`：默认 source/sink；
- `engine/test/c/`：Engine 端回归测试（`npm run test-c`）。

## 结果摘要

| 验收项 | 结果 |
| --- | --- |
| 1. 功能单测 | parser-C 50/50；Engine `test-c` 3/3 |
| 2. 靶场语义流通（自建 sast-c） | 65/65 检出，17/17 反例无误报 |
| 3. 大项目解析 | Redis、curl、SQLite 共 2,279 个文件、119 万行：0 崩溃，函数保留率 ≥100%；curl 命令行工具完整扫描 2 分 42 秒完成 |
| 4. 真实靶场命中率 | Juliet CWE-78、CWE-134（char + wchar_t，共 6,080 个测试用例）：TPR 100%，FPR 0%；CASTLE 污点类 CWE：TPR 100%，安全样本 FPR 62.5%（带输入校验的写法，见报告） |

详细数据和局限见 [四项验收报告](docs/C扩展-四项验收报告.md)。

## 快速运行

```bash
# parser 单测
cd uast/parser-C && npm install && npm test && npm run build

# Engine：安装依赖（package-lock 指向 npmmirror，若该镜像不可达可加以下两个参数）
cd ../../engine
npm ci --registry=https://registry.npmjs.org/ --replace-registry-host=registry.npmmirror.com
npm run test-c

# 扫描任意 C 项目
npx tsx src/main.ts --sourcePath <C 项目> --language c \
  --ruleConfigFile resource/example-rule-config/rule_config_c.json \
  --checkerPackIds taint-flow-c-default --report <输出目录>
```
