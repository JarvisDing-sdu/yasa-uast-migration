# OWASP Benchmark Python v0.1：旧 Python UAST Parser 基线

此文档记录 d 项的主靶场基线。它替代“用完整规则扫 xAST 合成样例”的做法：OWASP Benchmark Python 对每个 case 提供 CWE、正/负真值，适合衡量完整规则在大量 Python 安全 case 上是否因 parser 替换退化。

## 固定输入

| 项目 | 值 |
| --- | --- |
| 上游仓库 | `https://github.com/OWASP-Benchmark/BenchmarkPython.git` |
| 固定 commit | `f1291485808b66e20ddb6b01b10dc71b3df8c8ba` |
| 扫描目录 | `benchmarks/owasp-benchmark-python/testcode/` |
| Python case | 1,230 |
| 官方正样例 | 452 |
| 官方负样例 | 778 |
| expected CSV SHA-256 | `6396f37c97cfd0c018db3d8750095ce6c678a083f83620cfb3e88fe27a46bb0c` |
| testcode 文件树 SHA-256 | `821b26cc8b22b973584ea0ede24c2c641527c2205a0b6544421a469eb9e07bf0` |

OWASP v0.1 的 case 分布包括命令注入、代码注入、反序列化、路径遍历、SQL/XPath 注入、XSS、XXE、弱随机数等；总计 1,230 个带真值 case。

## 旧 parser 扫描配置

| 项目 | 值 |
| --- | --- |
| Engine | v0.3.2 / `249420d` |
| UAST parser | external `runtime/yasa-engine-v0.3.2/uast4py-linux-amd64` |
| 规则文件 | `runtime/yasa-engine-v0.3.2/example-rule-config/rule_config_python.json` |
| 已加载 checker | `taint_flow_python_input`、`taint_flow_python_input_inner`、`taint_flow_python_django_input` |
| 并行 worker | 1 |

完整扫描结果：

| 指标 | 结果 |
| --- | ---: |
| 扫描文件 | 1,230 |
| 代码行 | 79,391 |
| 分析入口 | 8,610 |
| 原始 SARIF finding | 190 |
| 去重后的命中测试文件 | 85 |
| Engine 总耗时 | 290,426 ms |
| parse 时间 | 20,309 ms |
| startAnalyze 时间 | 36,386 ms |
| symbolInterpret 时间 | 231,668 ms |
| 命令墙钟时间 | 295.58 s |
| 峰值 RSS | 1,528,644 KiB，约 1.46 GiB |
| SARIF SHA-256 | `a9a058a70b626edd0847b1e6c66593b7265a7cc33f4a8090c2130e427a7345a9` |

完整 SARIF 与扫描摘要位于 Git 忽略的：

```text
artifacts/owasp-benchmark-python-v0.1-old-uast4py-full-rules/
```

## 文件级真值评分

当前 YASA SARIF 没有携带 OWASP case 的 CWE/category 标识。因此先采用可重复的文件级匹配规则：只要某个 `BenchmarkTestNNNNN.py` 出现至少一条 SARIF finding，就把该 case 标记为“命中”。

| 结果 | 数量 |
| --- | ---: |
| TP：正样例且命中 | 41 |
| FN：正样例但未命中 | 411 |
| TN：负样例且未命中 | 734 |
| FP：负样例却命中 | 44 |

这不是 OWASP 官方的 CWE-aware score；它是用于 parser 替换前后回归的稳定比较口径。新 Node parser 必须对完全相同的 commit、规则和命令重跑，并用同一评分脚本比较 TP/FN/TN/FP、命中 case 集合、SARIF 位置与性能。

## 新 Tree-sitter parser 回归结果（2026-09-13）

已使用同一 OWASP commit、同一 1,230 文件输入、同一规则文件（SHA-256
`410ade9a71f419c56cb2e85fc38929bdb7807eaf0804161d007762caad4cdb2b`）、同一三个
checker 和单 worker，对 Node.js 进程内 Tree-sitter Python parser 重跑。

当前 Engine CLI 需要显式传入 `--checkerIds`；仅提供规则 JSON 会导致 checker 未加载、
产生无效的 0 finding 扫描。因此正式复现命令为：

```bash
cd engine
node --import tsx src/main.ts \
  --sourcePath ../benchmarks/owasp-benchmark-python/testcode \
  --language python \
  --analyzer PythonAnalyzer \
  --ruleConfigFile ../runtime/yasa-engine-v0.3.2/example-rule-config/rule_config_python.json \
  --checkerIds taint_flow_python_input,taint_flow_python_input_inner,taint_flow_python_django_input \
  --workerCount 1 \
  --report ../artifacts/owasp-benchmark-python-v0.1-new-tree-sitter-full-rules
```

| 指标 | 旧 external `uast4py` | 新 Tree-sitter parser | 结论 |
| --- | ---: | ---: | --- |
| 分析文件 | 1,230 | 1,230 | 一致 |
| 原始 SARIF finding | 190 | 190 | 一致 |
| 命中测试文件 | 85 | 85 | 一致 |
| TP / FN / TN / FP | 41 / 411 / 734 / 44 | 41 / 411 / 734 / 44 | 一致 |
| marked source | 109,176 | 109,176 | 一致 |
| matched sink | 9,436 | 9,436 | 一致 |
| entrypoint | 8,610 | 8,610 | 一致 |
| Engine 总时间 | 290,426 ms | 146,305 ms | 新快约 49.6% |
| parse 时间 | 20,309 ms | 7,393 ms | 新快约 63.6% |
| symbolInterpret 时间 | 231,668 ms | 121,296 ms | 新快约 47.6% |

新报告位于 Git 忽略的：

```text
artifacts/owasp-benchmark-python-v0.1-new-tree-sitter-full-rules/
```

SARIF 文件整体 SHA-256 不同，因为 trace location 附带的派生 `nodeHash` 不同：

```text
old: a9a058a70b626edd0847b1e6c66593b7265a7cc33f4a8090c2130e427a7345a9
new: 3b4707d7434669e4aa6444b30273ee17f1e1af1cf94a0d6399d4f2f029f4450a
```

但按 `ruleId`、文件、行列、消息比较，190 条 finding identity 完全一致；进一步从全部
SARIF result 中剔除派生 `nodeHash` 后，`codeFlow/threadFlow` 在内的完整 result JSON
完全一致。因此本次差异不是 source/sink、finding 位置或污点链差异，而是新旧 UAST 节点哈希
不同。严格峰值 RSS 尚未用同一 `/usr/bin/time -v` 口径重测；新扫描结束时 Node RSS 为
约 1,388 MB，不能直接与旧基线的 1.46 GiB peak RSS 作结论性比较。

## 当前污点 checker 覆盖范围内的 CWE 分类评分

全量 1,230 case 的 TP/FN/TN/FP 用于 parser 迁移回归，不能直接评价当前污点规则的绝对
安全能力：OWASP 同时包含弱 hash、弱随机数、cookie、XXE 等非 source→sink 问题。

依据当前 `rule_config_python.json` 实际配置的 `FuncCallTaintSink`，单独建立如下“当前
污点模型范围”评分：

```text
cmdi            os.system / subprocess 等命令执行 sink
codeinj         eval / exec sink
deserialization pickle.loads / yaml.load sink
pathtraver      open / rename / remove 等路径 sink
sqli            cursor.execute / session.execute 等 SQL sink
xss             fastapi.responses.HTMLResponse sink
```

不纳入该范围的 OWASP 类别：

```text
hash / weakrand / securecookie / xxe
```

它们应由 API、算法或配置 checker 评价，而不是以污点 checker 的 FN 评价。`ldapi`、
`xpathi`、`redirect` 当前规则没有直接配置的对应 sink，先列为待补规则，不纳入本范围。

运行方式是在同一份 1,230 case SARIF 上筛选 category 评分，不会替代全量回归：

```bash
python3 workstreams/yasa-python-migration/scripts/score_owasp_benchmark_python.py \
  --expected benchmarks/owasp-benchmark-python/expectedresults-0.1.csv \
  --sarif artifacts/owasp-benchmark-python-v0.1-new-tree-sitter-full-rules/report.sarif \
  --include-categories cmdi,codeinj,deserialization,pathtraver,sqli,xss \
  --scope-name current-python-taint-model \
  --out artifacts/owasp-benchmark-python-v0.1-new-tree-sitter-full-rules/taint-scope-score.json
```

| 指标 | old external parser | new Tree-sitter parser |
| --- | ---: | ---: |
| 纳入 category | 6 | 6 |
| 文件级 case | 400 | 400 |
| 官方正样例 | 152 | 152 |
| 官方负样例 | 248 | 248 |
| SARIF finding（属于该范围） | 172 | 172 |
| 命中文件 | 78 | 78 |
| TP | 38 | 38 |
| FN | 114 | 114 |
| TN | 208 | 208 |
| FP | 40 | 40 |

对应的范围内指标：

```text
recall      = 38 / 152 ≈ 25.0%
precision   = 38 / (38 + 40) ≈ 48.7%
specificity = 208 / 248 ≈ 83.9%
```

分类详情在 old/new 两侧完全一致：

| category | TP | FN | TN | FP | 观察 |
| --- | ---: | ---: | ---: | ---: | --- |
| cmdi | 5 | 8 | 5 | 2 | 有效但覆盖有限 |
| codeinj | 9 | 11 | 23 | 10 | 覆盖有限且误报较多 |
| deserialization | 6 | 12 | 35 | 1 | 误报较低，但漏报较多 |
| pathtraver | 13 | 52 | 87 | 16 | 覆盖不足 |
| sqli | 5 | 0 | 0 | 11 | 所有 16 文件都被命中，负样例精度差 |
| xss | 0 | 31 | 58 | 0 | 当前 sink/source 模型没有覆盖 OWASP XSS 写法 |

结论：新 parser 没有改变当前 checker 的任何分类能力；当前绝对召回和精度不足应归入
规则工坊工作。下一步应先补现有污点 checker 的 source/sink/sanitizer，再为 weak hash、
weak random、cookie、XXE 等类别设计独立 API/配置 checker。

复算命令：

```bash
python3 workstreams/yasa-python-migration/scripts/score_owasp_benchmark_python.py \
  --expected benchmarks/owasp-benchmark-python/expectedresults-0.1.csv \
  --sarif artifacts/owasp-benchmark-python-v0.1-old-uast4py-full-rules/report.sarif \
  --out artifacts/owasp-benchmark-python-v0.1-old-uast4py-full-rules/file-score.json
```
