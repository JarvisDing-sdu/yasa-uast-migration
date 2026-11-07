# 复现官方最新 Engine + C 的调用图对比

版本及校验和见 `C-callgraph-results.json` 的 manifest。最终 Engine 基底为官方提交 `59d223494f1de37d4f3277848db241418bfcd068`，在其上应用包内 C 适配补丁。不是直接运行旧 C fork。

## 重新准备分析引擎

使用 Node v24.16.0，保证 `node` 与 `npm` 使用同一运行时。在一个新目录执行：

```bash
git clone https://github.com/antgroup/YASA-Engine.git engine
git -C engine checkout 59d223494f1de37d4f3277848db241418bfcd068
git clone https://github.com/JarvisDing-sdu/yasa-uast.git uast
git -C uast checkout 3f2141f93be48299c5908afbd6c8e8720bae431e
```

在 `uast/parser-C` 目录执行 `npm ci --ignore-scripts`、`npm run build` 和 `npm test`。然后在 `engine` 目录应用包内 `Yasa-latest-engine-C-adaptation.patch`：

```bash
git apply /absolute/path/to/Yasa-latest-engine-C-adaptation.patch
npm ci --ignore-scripts
npm rebuild better-sqlite3
npm run test-c
npm run typecheck
```

若 lockfile 里的 npmmirror 不可达，可在 npm 命令中加 `--registry=https://registry.npmjs.org/ --replace-registry-host=registry.npmmirror.com`。C parser 是相邻目录的 file 依赖，必须先检出并构建上面的 UAST；engine lockfile 不会自动下载这份 Git 源码。测试和评测验证的是 TypeScript 源码运行方式，未生成新的发布二进制。

CodeGraph 使用正式发布版 v1.6.2。若使用官方 macOS arm64 发布包，其 SHA-256 必须为 `d74d1bfb4060db63ec3c2b72c4e17f76c31978af3bad6ace4370d1501ac0662e`。安装其他平台对应的同一版本也可以，但本报告只实测 macOS arm64。

## 重新运行

包内 `sources/kilo`、`sources/linenoise`、`sources/semantics` 为实际输入。也可以按 manifest 中的 Git commit 重新检出前两个项目。

在 engine 目录，将下面两个变量设成绝对路径；每个样本使用新的输出目录：

```bash
BENCH_SOURCE_ROOT=/absolute/path/to/sources/semantics
BENCH_REPORT_DIR=/absolute/path/to/new-yasa-report
node --import tsx src/main.ts \
  --sourcePath "$BENCH_SOURCE_ROOT" --language c \
  --cTarget macos --cUnknownMacros undefined \
  --checkerIds callgraph --dumpAllCG \
  --ruleConfigFile resource/example-rule-config/rule_config_c.json \
  --report "$BENCH_REPORT_DIR"
```

默认 C 分析模式只用于补充验证语义样本，将 `--checkerIds callgraph` 换成 `--checkerPackIds taint-flow-c-default`。

CodeGraph 对同一 source root 执行：

```bash
CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1 CODEGRAPH_NO_DAEMON=1 \
  codegraph init --yes "$BENCH_SOURCE_ROOT"
```

## 直接复算包内证据

不需要再运行分析引擎，Python 3.9+ 的标准库即可复算已有输出。在解压目录执行：

```bash
python3 evaluate_c_callgraph.py \
  --gold sources/semantics/gold.json --source-root sources/semantics \
  --yasa evidence/yasa/semantics/callgraph.json \
  --codegraph evidence/codegraph/semantics.db --output semantics-rescored.json

python3 evaluate_c_callgraph.py \
  --clang-ast evidence/clang/kilo-clang-ast.json --source-file kilo.c \
  --source-root sources/kilo --yasa evidence/yasa/kilo/callgraph.json \
  --codegraph evidence/codegraph/kilo.db --output kilo-rescored.json

python3 evaluate_c_callgraph.py \
  --clang-ast evidence/clang/linenoise-clang-ast.json --source-file linenoise.c \
  --source-root sources/linenoise --yasa evidence/yasa/linenoise/callgraph.json \
  --codegraph evidence/codegraph/linenoise.db --output linenoise-rescored.json
```

预期：kilo 双方 47/0/0；linenoise 双方 144/0/0；semantics Yasa 26/0/2、CodeGraph 16/2/12（均按 TP/FP/FN）。补充默认模式的 Yasa 输出在 `evidence/yasa/semantics-default/callgraph.json`，对同一 gold 应得 28/0/0。

## 参考与局限

主指标是去重内部函数对，不是调用点数量、外部库覆盖率或漏洞检测准召率。真实项目只统计主实现文件的内部直接调用；语义程序包含 20 条经 Clang 核对的直接边和 8 条预先人工标注的确定间接边。宏按 macOS/undefined 配置评估，`#if 0` 额外边在此配置下计为 FP。样本仅支持本报告的首轮小样本结论。

复现包保留 kilo、linenoise 的原始许可证文件及源码中的版权声明；C 适配来源和上游许可证保留在补丁及对应 Git 仓库中。
