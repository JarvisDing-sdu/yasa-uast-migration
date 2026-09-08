# Python UAST Parser 迁移：测试、靶场与验收说明

本文说明把 YASA Python UAST parser 从外部 `uast4py` 二进制迁移到 Node.js 进程内实现时，如何理解老师提出的验收项、现有测试数据来自哪里，以及应当怎样建立和执行回归。

当前范围是 **Python parser**。当前阶段明确不做 Go；不建立 Go parser、Go 靶场或 Go 完整规则基线。若老师后续重新要求 Go，需要另行建立其旧 parser 基线，不能把 Python 结果外推到 Go。

## 1. 当前系统的工作方式

迁移前，Python 的解析路径为：

```text
.py 源码
  -> Engine 启动外部 uast4py
  -> uast4py 内部使用 Python ast.parse()
  -> UASTTransformer 转换为 UAST
  -> 写入 UAST JSON
  -> Engine 读回 JSON，补 parent/sourcefile/nodehash
  -> PythonAnalyzer 做符号执行、污点分析和 SARIF 输出
```

迁移目标是把“外部进程、临时文件、JSON 落盘再读回”的 parser 部分替换为 Node.js 进程内实现；不能改变 UAST 语义和 Engine 可观察的分析结果。

## 2. 老师提出的五项任务

| 项目 | 要求 | 证明什么 |
| --- | --- | --- |
| a. UAST 单测回归 | 测试 Python 源码到 UAST 的节点、字段、位置和错误语义 | 新 parser 转树没有改变既有语义 |
| b. 大项目 AST 解析与还原 | 用大型真实 Python 项目全量解析；导出、重读 UAST 并交给 Engine 消费 | 不只小样例可用；目录扫描、序列化、位置和内存也可靠 |
| c. YASA xAST 回归通过 | 用 Engine 官方 xAST Python benchmark 和其历史预期结果回归 | 通用污点引擎没有因 UAST 改变而退化 |
| d. 开源靶场项目 Py、Go 检出能力不下降 | 当前阶段只做 Python：使用 OWASP Benchmark Python v0.1 的 1,230 个有 CWE/正负真值 case，用完整规则比较旧 parser 与新 parser | Python 完整规则检出能力与误报能力不下降；Go 当前不在范围内 |
| e. 性能 | 在同一机器、同一输入、同一规则下比较旧 binary 和新 Node parser | 时间、吞吐、内存和失败率不退化 |

推荐执行顺序：

```text
先记录旧 parser 的 c + 性能基线
  -> 补 a 的 UAST golden / 单测
  -> 实现 Node parser
  -> 重跑 a、c
  -> 做 b、d、e 的正式验收
```

## 3. 基线

基线是“替换前已经确认正确、以后可重复比较的结果”。本项目已有的 Python 最小基线记录在 [python-baseline.md](python-baseline.md)：

```text
Engine: v0.3.2 / 249420d
UAST: v0.2.18 / 07e3823
旧 parser: runtime/uast-v0.2.18/uast4py-linux-amd64
```

已记录并复跑的项目包括：

1. `uast/parser-Python/test/test_compat_keywords.py`：8 个小型 parser 单测通过；
2. `test_type_annotations.py`：源码 parser 与官方 binary 的 UAST JSON 结构相同，886 个节点；
3. xAST 的 `assign_expression_stmt_001_T.py`：两种 parser 的 UAST JSON 相同，46 个节点；
4. 一个 Engine smoke：`taint_src -> result -> taint_sink -> os.system`，得到 1 个 finding。

这些是最小基线；它们不能替代完整 xAST 回归和性能基线。

## 4. 测试样例分层

### 4.1 UAST parser 自带小样例

位置：

```text
uast/parser-Python/test/
```

代表文件：

```text
test_compat_keywords.py
test_type_annotations.py
```

用途：验证小而精确的转换规则，例如 `async`/`await` 兼容、类型注解、真实语法错误等。它们是单元测试，不是完整安全扫描。

### 4.2 Engine 自带小样例

位置：

```text
engine/test/python/no-init-dispatch-cases/
engine/test/python/fastapi-backgroundtasks-cases/
engine/test/php/checker-cases/
engine/test/callchain/
```

用途：验证某个已知 Engine 行为或历史 bug。例如 Python 的无显式 `__init__` 方法派发、继承和正负污点样例；FastAPI `BackgroundTasks.add_task()` 的回调识别与污点链。

这些样例随 Engine 提交，体积小、失败时定位快。`expect/` 下的文件是历史 finding/污点链快照，不是 Python 源码样例。

### 4.3 xAST 大靶场

xAST 是独立开源项目：

```text
https://github.com/alipay/ant-application-security-testing-benchmark
```

当前工作区已有两份独立 clone：

```text
benchmarks/xast-python/
benchmarks/xast-go/
```

其 Python 3 SAST 输入位于：

```text
benchmarks/xast-python/sast-python3/case/
```

其 Python 2 SAST 输入位于：

```text
benchmarks/xast-python/sast-python2/case/
```

当前官方 Engine Python benchmark 只覆盖 **Python 3**，不覆盖 Python 2。Python 2 只有在需求明确要求老 Python 代码兼容时，才应另建“旧 parser 已支持部分不得退化”的基线；不应默认承诺完整 Python 2 语法支持。

## 5. c：YASA xAST 回归究竟测什么

c 使用的测试规则是：

```text
engine/test/python/rule_config_xast_python3.json
```

它只有一个人为固定的污点模型：

```text
source: 名为 taint_src 的变量/参数
sink:   os.system(...) 的第 0 个参数
checker: taint_flow_test
```

含义是：若 `taint_src` 经赋值、参数、返回值、字段、集合、分支、循环、闭包、继承或跨文件调用等路径，最终进入 `os.system` 的第一参数，则应报告 finding。

```python
def demo(taint_src):
    result = taint_src
    os.system(result)  # 应报告潜在命令注入
```

这不是产品级完整安全规则集。它的作用是固定 source/sink、隔离框架规则差异，纯粹验证 parser/UAST/通用数据流引擎有没有退化。xAST 的数百个 case 改变的是中间数据流结构，不是 source/sink 名称。

因此：

```text
c = 通用污点引擎 xAST 回归
d = 使用真实、多规则配置的安全检测能力对比
```

## 6. xAST 数据如何导入 Engine 测试

Engine 不把完整 xAST 靶场直接提交进 Git。原因包括数据量、独立仓库维护和只下载所需语言；源码通过 `.gitignore` 忽略本地 benchmark 缓存：

```text
engine/test/python/benchmarks/
engine/test/go/benchmarks/
```

官方 Python 数据准备脚本：

```text
engine/test/python/prepare-python-benchmark.ts
```

它会：

```text
clone xAST 的 main-forYasaTest 分支
  -> 只保留 sast-python3/
  -> 将 sast-python3/case/ 移到
     engine/test/python/benchmarks/sast-python3/case/
```

随后官方 benchmark：

```text
engine/test/python/test-python-benchmark.ts
```

扫描：

```text
engine/test/python/benchmarks/sast-python3/
```

并将实际输出与：

```text
engine/test/python/expect/pythonbenchmark-expect.result
```

逐条比较。该预期文件记录的是历史 finding、sink 位置和污点链，不是测试源码。

### 注意事项

- `npm run test-python` **不会自动**运行准备脚本；目录不存在时 benchmark 测试会跳过；
- 准备脚本会在需要准备时清理目标 benchmark 目录后再 clone，因此不要在未知目录内容时重复运行；
- 正式迁移前后对比必须使用完全相同的 xAST commit、规则和目录；
- 当前工作区的 `benchmarks/xast-python/` 可用于额外对照，但不要直接混入官方 Engine benchmark 目录后就拿历史预期文件比较，因为两者可能不是同一 xAST 版本。

## 7. 执行 c 与性能基线的计划

### 7.1 准备条件

1. 安装 Engine 的 Node 依赖；
2. 通过官方准备脚本取得 Python 3 benchmark；
3. 记录 xAST 分支与最终 commit SHA；
4. 确保旧 `uast4py` binary 可由 Engine 找到；
5. 固定 Engine/UAST、规则文件、机器和运行参数。

### 7.2 迁移前（旧 binary）

运行完整 Python 3 xAST benchmark，保存：

```text
扫描文件数
解析成功/失败的文件及失败原因
finding 数和完整污点链
SARIF
总耗时
Engine parse 阶段耗时
峰值内存
xAST commit、规则文件 hash、版本信息
```

结果应放在工作区的 `artifacts/`（该目录不提交）和一份可提交的摘要文档中。

2026-09-07 已完成这一步的官方 Python 3 xAST 基线：`main-forYasaTest` / `32a74f8`，606 个 Python 文件，332 个 finding，官方快照比较 `332 passing`；Engine 总扫描时间 8,605 ms，shell 墙钟时间 10.44 s，峰值 RSS 约 446 MiB。详见 [python-baseline.md](python-baseline.md)。

### 7.3 迁移后（Node parser）

使用完全相同的输入和命令重跑。比较：

```text
_T.py：原来应检出的不能漏报
_F.py：不能新增误报
finding、sink、位置和污点链不应意外改变
解析成功/失败文件列表不应退化
时间、吞吐、内存和失败率不应退化
```

## 8. 编辑器中的 __dirname 提示

`test-python-benchmark.ts` 中的 `__dirname` 是 Node.js/CommonJS 运行时提供的“当前文件目录”。例如：

```ts
path.resolve(__dirname, 'benchmarks/sast-python3/')
```

会解析为 `engine/test/python/benchmarks/sast-python3/`。

若编辑器显示 `Cannot find name '__dirname'. ts(2304)`，通常不是脚本运行时错误，而是：

- Engine 的 `tsconfig.json` 只包含 `src/`，排除了 `test/`；
- 本地没有安装 `engine/node_modules/`，编辑器无法加载 Node 类型。

在真正执行 Engine 测试前安装依赖并让编辑器加载 Node 类型即可；本次 parser 迁移不需要为该提示修改测试脚本。

## 9. 当前阶段的下一步

在修改 parser 前：

1. 准备官方 `sast-python3/case` benchmark；
2. 用旧 external `uast4py` 跑 c，并记录能力/性能基线；
3. 补充 Python AST -> UAST 的代表性 golden 样例；
4. 再开始 Node parser 实现。
