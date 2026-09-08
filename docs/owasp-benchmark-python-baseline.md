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

复算命令：

```bash
python3 scripts/score_owasp_benchmark_python.py \
  --expected benchmarks/owasp-benchmark-python/expectedresults-0.1.csv \
  --sarif artifacts/owasp-benchmark-python-v0.1-old-uast4py-full-rules/report.sarif \
  --out artifacts/owasp-benchmark-python-v0.1-old-uast4py-full-rules/file-score.json
```
