# Python UAST 基线（中文）

本文是 [python-baseline.md](python-baseline.md) 的中文说明，用于 Python parser 从外部 `uast4py` binary 迁移到 Node.js 进程内实现前后的回归比较。

日期：2026-09-07

## 固定版本

```text
YASA-Engine：v0.3.2（249420d）
YASA-UAST：v0.2.18（07e3823）
旧 Python UAST parser：runtime/yasa-engine-v0.3.2/uast4py-linux-amd64
源码 parser 测试解释器：Python 3.10.12
```

## 已确认的小型基线

1. Python parser 兼容性单测：`8 passed, 0 failed`。

   覆盖旧代码把 `async` / `await` 当标识符、正常异步语法、类型节点序列化和真实语法错误。

2. 源码 parser 与官方 binary 的 UAST JSON 等价比较。

   | 输入 | 节点数 | 结果 |
   | --- | ---: | --- |
   | `uast/parser-Python/test/test_type_annotations.py` | 886 | 结构完全相同 |
   | xAST `assign_expression_stmt_001_T.py` | 46 | 结构完全相同 |

   比较时只排除机器相关的 `sourcefile` 字段；其余 JSON 结构必须一致。

3. 单个 xAST Engine smoke。

   ```text
   taint_src -> result -> taint_sink -> os.system
   ```

   预期并已得到 1 个 finding 与 SARIF 污点链。

## 完整 xAST Python 3 回归与性能基线

这是迁移前的正式 c 项基线：使用旧外部 `uast4py`，尚未引入 Node.js Python parser。

| 项目 | 值 |
| --- | --- |
| xAST 分支 | `main-forYasaTest` |
| xAST commit | `32a74f8dec9dcacfd99a9053ebd8b545a34e09c7` |
| 输入目录 | `engine/test/python/benchmarks/sast-python3/case/` |
| Python 文件数 | 606 |
| 输入树 SHA-256 | `62a62ed07a3317322ceda4268ef57012305e77cfe94c286d34eeb803b2b51ae0` |
| Engine 执行方式 | `npm run test-python` |
| 使用规则 | `engine/test/python/rule_config_xast_python3.json` |
| 检查器 | `taint_flow_test` |

规则含义：把名为 `taint_src` 的变量/参数当作污染源；若污点最终进入 `os.system(...)` 的第一个参数，就产生 finding。这是测试通用数据流引擎的固定探针，不是完整的产品级安全规则集。

测试结果：

```text
332 passing
历史预期 finding：332
实际 finding：332
```

| 扫描指标 | 结果 |
| --- | ---: |
| 扫描文件 | 606 |
| 代码行数 | 17,440 |
| Finding | 332 |
| 标记的污染源 | 1,993 |
| 匹配的 sink | 3,682 |
| 入口点 | 1,295 |
| Engine 总扫描时间 | 8,605 ms |
| 解析总时间 | 2,969 ms |
| 其中 parseCode | 1,589 ms |
| 其中 preload | 23 ms |
| 其中 processModule | 1,333 ms |
| startAnalyze | 1,428 ms |
| symbolInterpret | 3,103 ms |
| 命令墙钟时间 | 10.44 s |
| 峰值 RSS | 456,596 KiB，约 446 MiB |
| 测试报告的污点链 hop 准确率 | 93.67%（1,391 / 1,485） |

详细 SARIF、扫描摘要和 diagnostics 位于本地、被 Git 忽略的：

```text
engine/test/python/report/
```

准备后的 xAST 靶场也位于被 Git 忽略的：

```text
engine/test/python/benchmarks/sast-python3/
```

## 完整 Python 规则扫描（补充观察，不是 d 的充分验收）

上面的 `taint_src -> os.system` 固定探针只用于 c，不能代表产品级安全规则。因此另用发布包提供的较完整 Python 配置，对同一批 606 个 xAST Python 3 文件做了一次补充扫描，记录迁移前结果。

| 项目 | 值 |
| --- | --- |
| 规则文件 | `runtime/yasa-engine-v0.3.2/example-rule-config/rule_config_python.json` |
| 规则文件 SHA-256 | `410ade9a71f419c56cb2e85fc38929bdb7807eaf0804161d007762caad4cdb2b` |
| 已加载 checker | `taint_flow_python_input`、`taint_flow_python_input_inner`、`taint_flow_python_django_input` |
| source 规则条目 | 64 |
| sink 规则条目 | 63 |
| Finding | 42 |
| 标记污染源 | 2,661 |
| 匹配 sink | 22,084 |
| 入口点 | 1,295 |
| Engine 总扫描时间 | 19,694 ms |
| 解析总时间 | 5,924 ms |
| symbolInterpret | 11,718 ms |
| 命令墙钟时间 | 21.07 s |
| 峰值 RSS | 421,732 KiB，约 412 MiB |
| SARIF SHA-256 | `c73c92b576195114cb5fdbf05880c897cd184c400fc7842c73ef3720064f12f2` |

详细结果保存在本地、被 Git 忽略的：

```text
artifacts/xast-python3-full-rule-baseline/
```

新 Node parser 可以使用同一输入和规则重跑，并比较 finding 的数量、身份、sink 位置和污点链，不能只比较“42”这个总数。

### 为什么完整规则只有 42 个 finding

这不是规则没有加载：扫描实际加载了 3 个 checker，标记了 2,661 个 source，匹配了 22,084 个 sink。42 是最终被证实从某个已识别 source 流到某个已识别 sink 的 finding 数。

但 xAST Python 3 大部分 case 是为通用数据流能力设计的合成样例，通常把污染源命名为 `taint_src`；完整规则配置中 **没有** 名为 `taint_src` 的 source 条目（检查结果为 0 条）。完整规则主要识别 `read`、`urlopen`、`getenv`、`request`、`json` 等真实 API 或框架来源。因此：

```text
332（小规则）= 人工 taint_src 作为 source 的通用数据流回归
42（完整规则） = 真实 API/框架 source 与真实 sink 在同一 xAST 样例中恰好相交的结果
```

所以 42 对这组“完整规则 + 合成 xAST 输入”是可解释的补充观察数据，但不能单独说明完整产品规则的覆盖率或召回率很高，也不是 d 的充分验收。若要评估真实漏洞检出，需要另选包含 Flask/Django/FastAPI、文件读取、HTTP 请求等真实 source/sink 的开源应用并建立单独基线。

### 当前范围决定

本阶段明确 **不做 Go**。不建立 Go parser、Go 靶场或 Go 完整规则基线。若老师后续重新要求 Go，再单独补建 Go 基线，不能把本次 Python 结果外推到 Go。

## 迁移后的验收要求

新 Node parser 必须在完全相同的输入、规则、Engine 版本和运行环境下重跑，并至少保持：

1. 兼容性单测继续通过；
2. 两个已记录样例的 UAST JSON 等价；
3. 单个 xAST smoke 的 finding 和 SARIF 链不变；
4. 完整 xAST Python 3 回归仍为 332 个预期 finding，332 个断言通过；
5. 不新增解析失败、漏报或误报；
6. 性能与峰值内存不发生未经批准的退化。
