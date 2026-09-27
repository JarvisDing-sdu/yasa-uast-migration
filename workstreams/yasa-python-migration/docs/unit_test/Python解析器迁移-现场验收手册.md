# Python parser 迁移：现场验收手册

> 适用工作区：`/home/dys1013/projects/yasa-uast-migration`
> 验收范围：Python，YASA-Engine v0.3.2、YASA-UAST v0.2.18 基线
> 建议：现场先展示已有报告和 artifact，再执行快速复算；不要临时覆盖正式 artifact。

## 0. 开始前确认版本和目录

```bash
cd /home/dys1013/projects/yasa-uast-migration

git log -1 --oneline
git -C engine log -1 --oneline
git -C uast log -1 --oneline
git submodule status

node --version
python3 --version
```

当前应至少看到：

```text
主仓库：c573b62 docs: classify remaining Python UAST differences
UAST：  fc91045 fix: preserve Python f-string and splat semantics
```

总览报告：

```text
workstreams/yasa-python-migration/docs/Python解析器迁移-最新进展与验收状态.md
```

## a. UAST 单测回归

### 验收目的

验证新 Tree-sitter parser 能构建、常用 Python 语义节点可解析、关键回归用例通过；同时验证
PythonEmitter 对已支持节点确定性生成，遇到未知节点 fail-closed。

### 现场推荐命令

```bash
cd /home/dys1013/projects/yasa-uast-migration/uast/parser-Python
npm run build
npm test
```

预期：TypeScript 构建成功，`parser.test.ts` 和 `semantic-matrix.test.ts` 通过，0 fail。

产物位置：

```text
uast/parser-Python/dist/    npm run build 的编译产物
终端输出                    npm test 的测试结果；不生成 SARIF 或 JSON 文件
```

其中语义矩阵包含 19 类小样例。普通 `npm test` 未设置 oracle 时，与旧 visitor 比较的用例
会跳过；如现场需要展示 old/new visitor 对比，再运行：

```bash
PYTHON_UAST_ORACLE="$PWD/.venv/bin/python" npm test
```

旧 parser 历史兼容用例单独运行：

```bash
"$PWD/.venv/bin/python" test/test_compat_keywords.py
```

Emitter 单测：

```bash
cd /home/dys1013/projects/yasa-uast-migration/uast/emitter-Python
npm test
```

预期输出包含：

```text
python-emitter unit tests passed
```

产物位置：Emitter 单测只输出到终端，不写测试报告文件。

### 报告

- `workstreams/yasa-python-migration/docs/Python-UAST语义单测.md`
- `workstreams/yasa-python-migration/docs/Python-Tree-sitter-实现总结.md`
- `workstreams/yasa-python-migration/docs/Python-Tree-sitter-迁移说明.md`

## b. 大项目 AST 解析与源码还原

### 验收目的

验证两件事：

```text
旧/new parser 直接 UAST 是否兼容；
UAST → PythonEmitter → Python → parser → UAST 是否 round-trip。
```

对于可执行小样例，还比较原始程序与还原程序的运行结果。

### Phase 1：20 个可执行 PyTorch 小样例

快速查看现成结果：

```bash
cd /home/dys1013/projects/yasa-uast-migration

python3 -c 'import json; p="workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/phase1-old-new-emitter-summary.json"; s=json.load(open(p)); print({k:v for k,v in s.items() if k not in ("cases","timingSeconds")})'

python3 -c 'import json; p="workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/phase1-old-new-emitter-runtime-summary.json"; s=json.load(open(p)); print({k:v for k,v in s.items() if k not in ("cases","timingSeconds")})'
```

预期关键结果：

```text
total = 20
oldParsed/newParsed = 20/20
oldEmitted/newEmitted = 20/20
semanticCanonicalUastEqual = 20/20
sourceTextEqual = 20/20
oldRuntimePassed/newRuntimePassed = 20/20
oldRoundtripSemanticUastPassed/newRoundtripSemanticUastPassed = 20/20
fullyPassed = 20/20
```

这两条查看命令读取的已有产物位置：

```text
workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/
├── phase1-old-new-emitter-summary.json
└── phase1-old-new-emitter-runtime-summary.json
```

如需完整重跑：

```bash
python3 workstreams/dl-cross-language-research/scripts/build_old_new_emitter_phase1.py \
  --old-binary runtime/uast-v0.2.18/uast4py-linux-amd64

workstreams/dl-cross-language-research/.venv/bin/python \
  workstreams/dl-cross-language-research/scripts/verify_old_new_emitter_phase1.py \
  --python workstreams/dl-cross-language-research/.venv/bin/python
```

完整重跑后的产物位置：

```text
workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/
├── DL001_tensor_literal/
│   ├── uast.old.json
│   ├── uast.new.json
│   ├── source.old.py
│   ├── source.new.py
│   ├── emitter.old.report.json
│   ├── emitter.new.report.json
│   ├── uast.old.roundtrip.new-parser.json
│   └── uast.new.roundtrip.new-parser.json
├── ... DL020_softmax/
├── phase1-old-new-emitter-summary.json
└── phase1-old-new-emitter-runtime-summary.json
```

### Phase 2：122 个真实 PyTorch 文件

快速查看汇总：

```bash
python3 -c 'import json; p="workstreams/dl-cross-language-research/artifacts/pytorch-upstream-old-new-emitter/summary.json"; s=json.load(open(p)); keys=["total","oldParsed","newParsed","semanticOldNewUastEqual","oldEmitted","newEmitted","oldRoundtripPassed","newRoundtripPassed","fullyPassed"]; print({k:s[k] for k in keys})'
```

预期：

```text
total = 122
oldParsed/newParsed = 122/122
semanticOldNewUastEqual = 106/122
oldEmitted/newEmitted = 75/122
oldRoundtripPassed = 39/122
newRoundtripPassed = 40/122
fullyPassed = 39/122
```

这条查看命令读取：

```text
workstreams/dl-cross-language-research/artifacts/
└── pytorch-upstream-old-new-emitter/
    └── summary.json
```

完整重跑约需两分钟：

```bash
python3 workstreams/yasa-python-migration/scripts/verify_old_new_emitter_corpus.py \
  --source-dir workstreams/dl-cross-language-research/benchmarks/pytorch-upstream \
  --artifact-dir workstreams/dl-cross-language-research/artifacts/pytorch-upstream-old-new-emitter \
  --old-binary runtime/uast-v0.2.18/uast4py-linux-amd64
```

完整重跑会更新：

```text
workstreams/dl-cross-language-research/artifacts/
└── pytorch-upstream-old-new-emitter/
    ├── summary.json
    └── <每个相对源码路径>/<文件名>/
        ├── uast.old.json
        ├── uast.new.json
        ├── source.old.py
        ├── source.new.py
        ├── emitter.old.report.json
        ├── emitter.new.report.json
        ├── uast.old.roundtrip.new-parser.json
        └── uast.new.roundtrip.new-parser.json
```

### 报告

- `workstreams/yasa-python-migration/docs/Python-UAST双侧还原-小样例.md`
- `workstreams/yasa-python-migration/docs/PyTorch真实源码-解析与还原.md`
- `workstreams/yasa-python-migration/docs/PyTorch旧新UAST差异分类.md`

### 现场结论

不能说“122 个文件全部无损还原”。正确说法是：122/122 可解析；20/20 可执行小样例双侧
运行与 round-trip 通过；真实大项目量化了可还原范围和信息损失；47 个文件触发同一类
comprehension lowering 后的 emitter fail-closed；剩余 16 个 old/new 差异全部有证据分类。

## c. YASA xAST 回归

### 验收目的

比较 parser 替换前后同一 xAST 合成靶场的 finding 身份和完整污点 trace，而不只比较总数。

### 现场扫描、比较与查看

先运行旧 external `uast4py` 基线：

```bash
cd /home/dys1013/projects/yasa-uast-migration

mkdir -p runtime/yasa-engine-v0.3.2/uast4py
ln -sfn ../uast4py-linux-amd64 runtime/yasa-engine-v0.3.2/uast4py/uast4py

runtime/yasa-engine-v0.3.2/yasa-engine-linux-x64 \
  --sourcePath engine/test/python/benchmarks/sast-python3/case \
  --language python \
  --analyzer PythonAnalyzer \
  --ruleConfigFile engine/test/python/rule_config_xast_python3.json \
  --checkerIds taint_flow_test \
  --workerCount 1 \
  --uastSDKPath runtime/yasa-engine-v0.3.2 \
  --report engine/test/python/report
```

预期旧基线：606 文件、332 findings、1,993 marked sources、3,682 matched sinks、1,295
entrypoints。

旧基线扫描产物：

```text
engine/test/python/report/
├── report.sarif
├── scan_summary.json
└── yasa-diagnostics-log.txt

logs/
├── yasa.YYYY-MM-DD.log
└── yasa-error.YYYY-MM-DD.log
```

然后运行新 Tree-sitter parser：

```bash
cd /home/dys1013/projects/yasa-uast-migration/engine

node --import tsx src/main.ts \
  --sourcePath test/python/benchmarks/sast-python3/case \
  --language python \
  --analyzer PythonAnalyzer \
  --ruleConfigFile test/python/rule_config_xast_python3.json \
  --checkerIds taint_flow_test \
  --workerCount 1 \
  --report /tmp/yasa-xast-acceptance
```

预期扫描结果：606 个文件、332 findings。

新扫描产物：

```text
/tmp/yasa-xast-acceptance/
├── report.sarif
├── scan_summary.json
└── yasa-diagnostics-log.txt
```

```bash
cd /home/dys1013/projects/yasa-uast-migration

python3 workstreams/yasa-python-migration/scripts/compare_yasa_sarif.py \
  --old engine/test/python/report/report.sarif \
  --new /tmp/yasa-xast-acceptance/report.sarif \
  --out /tmp/xast-acceptance-diff.json
```

预期：

```text
oldRawFindings = 332
newRawFindings = 332
identityEqual = true
normalizedResultsEqual = true
firstNormalizedDifference = null
oldOnlyIdentities/newOnlyIdentities = []/[]
```

比较产物：

```text
/tmp/xast-acceptance-diff.json
```

需要在 Cursor 查看本次扫描的路径和污点链时：

```bash
python3 workstreams/yasa-python-migration/scripts/prepare_sarif_for_viewer.py \
  --input /tmp/yasa-xast-acceptance/report.sarif \
  --output /tmp/yasa-xast-acceptance/report.viewer.sarif \
  --source-root engine/test/python/benchmarks/sast-python3/case
```

在 Cursor 中只打开 `/tmp/yasa-xast-acceptance/report.viewer.sarif`。

Viewer 产物：

```text
/tmp/yasa-xast-acceptance/report.viewer.sarif
```

### 报告

```text
workstreams/yasa-python-migration/docs/xAST-检出与性能对比.md
```

## d. 开源靶场检出能力不下降

### 验收目的

使用固定 OWASP Benchmark Python v0.1、相同规则和 checker，比较旧/new parser 的 finding、
trace 和 TP/FN/TN/FP。该项证明 parser 替换不降低现有检出能力，不代表规则绝对效果很好。

### 现场扫描、比较与评分

```bash
cd /home/dys1013/projects/yasa-uast-migration/engine

node --import tsx src/main.ts \
  --sourcePath ../benchmarks/owasp-benchmark-python/testcode \
  --language python \
  --analyzer PythonAnalyzer \
  --ruleConfigFile ../runtime/yasa-engine-v0.3.2/example-rule-config/rule_config_python.json \
  --checkerIds taint_flow_python_input,taint_flow_python_input_inner,taint_flow_python_django_input \
  --workerCount 1 \
  --report /tmp/yasa-owasp-acceptance
```

预期：1,230 文件、190 findings、85 个命中文件，TP/FN/TN/FP 为
`41/411/734/44`。

新扫描产物：

```text
/tmp/yasa-owasp-acceptance/
├── report.sarif
├── scan_summary.json
└── yasa-diagnostics-log.txt
```

```bash
cd /home/dys1013/projects/yasa-uast-migration

python3 workstreams/yasa-python-migration/scripts/compare_yasa_sarif.py \
  --old artifacts/owasp-benchmark-python-v0.1-old-uast4py-full-rules/report.sarif \
  --new /tmp/yasa-owasp-acceptance/report.sarif \
  --out /tmp/owasp-acceptance-diff.json

python3 workstreams/yasa-python-migration/scripts/score_owasp_benchmark_python.py \
  --expected benchmarks/owasp-benchmark-python/expectedresults-0.1.csv \
  --sarif /tmp/yasa-owasp-acceptance/report.sarif \
  --out /tmp/yasa-owasp-acceptance/file-score.json
```

预期比较结果：

```text
oldRawFindings/newRawFindings = 190/190
identityEqual = true
normalizedResultsEqual = true
oldOnlyIdentities/newOnlyIdentities = []/[]
```

比较和评分产物：

```text
/tmp/owasp-acceptance-diff.json
/tmp/yasa-owasp-acceptance/file-score.json
```

需要在 Cursor 查看本次扫描的路径和污点链时：

```bash
python3 workstreams/yasa-python-migration/scripts/prepare_sarif_for_viewer.py \
  --input /tmp/yasa-owasp-acceptance/report.sarif \
  --output /tmp/yasa-owasp-acceptance/report.viewer.sarif \
  --source-root benchmarks/owasp-benchmark-python/testcode
```

在 Cursor 中只打开 `/tmp/yasa-owasp-acceptance/report.viewer.sarif`。

Viewer 产物：

```text
/tmp/yasa-owasp-acceptance/report.viewer.sarif
```

### 报告

```text
workstreams/yasa-python-migration/docs/OWASP-Python-旧新回归.md
```

## e. 性能

### 当前可以验收的内容

最新独立复测已经记录多轮中位数：

```text
xAST：
new 墙钟 2,713 ms，legacy 4,020 ms
new parseCode 520 ms，legacy 1,825 ms
RSS 556.1 MB / 563.4 MB

OWASP：
new 墙钟 60,697 ms，legacy 69,752 ms
new parseCode 1,605 ms，legacy 14,074 ms
RSS 2,886 MB / 2,177 MB
```

现场查看：

```bash
rg -n "本机性能|端到端墙钟|parseCode|峰值 RSS" \
  workstreams/yasa-python-migration/docs/xAST-检出与性能对比.md \
  workstreams/yasa-python-migration/docs/OWASP-Python-旧新回归.md
```

单次 xAST 计时演示：

```bash
cd /home/dys1013/projects/yasa-uast-migration/engine

/usr/bin/time -v node --import tsx test/python/tree-sitter-scan-runner.ts \
  new test/python/benchmarks/sast-python3/case
```

该计时命令的性能数据打印在终端；它不写 JSON 或 SARIF。长期性能结论查看下方两份 Markdown
报告，不要把单次终端耗时当作最终中位数。

### 必须说明的限制

当前 legacy 对照 runner 通过子进程调用 CPython visitor；`/usr/bin/time` 记录的父 Node RSS
不包含子 Python 进程峰值。OWASP 新侧 RSS 也有明显波动。因此可以验收“解析时间与端到端时间
已有多轮数据”，但不能据当前数字下结论说新 parser 一定更省内存。

若对方要求双方完全相同进程树口径的 peak RSS，e 项仍需补做统一 cgroup/container 统计或
能够汇总父子进程峰值的监控；不要把当前 RSS 表格解释为 parser 自身的严格内存对比。

### 报告

- `workstreams/yasa-python-migration/docs/xAST-检出与性能对比.md`
- `workstreams/yasa-python-migration/docs/OWASP-Python-旧新回归.md`

## 建议的现场演示顺序

时间紧时只执行：

1. a：`npm run build`、`npm test`、PythonEmitter `npm test`；
2. b：打印两个 Phase 1 summary 和一个 122 文件 summary；
3. c：运行 xAST SARIF 比较器；
4. d：运行 OWASP SARIF 比较器和 `sha256sum`；
5. e：打开两份性能报告，明确 RSS 口径限制。

预计快速演示不含全量扫描时约 3–5 分钟。完整重跑 PyTorch、xAST、OWASP 会显著延长时间。

## 交付边界提醒

`workstreams/dl-cross-language-research/` 目前是本机独立私有仓库。b 项 Phase 1 的 Python-only
脚本与生成 artifact 在本机可验收，但公开仓库的新克隆不会自动包含它们。最终企业交付前，
应把 Phase 1 所需的 Python-only manifest 和验证脚本迁入
`workstreams/yasa-python-migration/`；PyTorch、DJL、WebDNN 多语言研究仍保持私有。
