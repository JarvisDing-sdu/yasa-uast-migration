# PyTorch Phase 1：Python UAST emitter 回转验证记录

## 1. 这次完成的事情

本次没有修改 Python parser，也没有修改 Engine。新增的是一个**反向源码生成器**：

```text
Python UAST JSON
    ↓
PythonEmitter（Node.js 内部运行）
    ↓
规范化的 roundtrip.py
```

它的任务不是还原作者原来的空格、注释和写法，而是在只读取 UAST 的前提下，生成一份
可执行、可重新解析的 Python 源码。相同 UAST 输入永远应产生字节级相同的输出。

完整的验证链路是：

```text
source.py
  ├─ 旧 uast4py parser → source.uast.json → PythonEmitter → roundtrip.py
  │                                                       ├─ Python + torch 执行 → 比较 expected.json
  │                                                       └─ 旧 uast4py parser → roundtrip.uast.json
  └─ Python + torch 执行 → expected.json

canonical(source.uast.json) == canonical(roundtrip.uast.json)
```

其中 `canonical` 只移除行列号和源文件路径；节点类型、字段、操作符、参数顺序和 metadata
都会比较。`expected.json` 仅由测试脚本读取，emitter 本身绝不会读取原始源码、运行答案或
`loc.sourcefile` 指向的文件。

## 2. 本次新增或修改的文件

### 真正的 emitter 代码

| 文件 | 作用 |
| --- | --- |
| `uast/emitter-Python/src/python-emitter.js` | `PythonEmitter` 本体。递归把 Python UAST 节点生成 Python 文本；未知节点抛出 `UnsupportedNodeError`，不会静默丢失。 |
| `uast/emitter-Python/src/cli.js` | 命令行封装：读取 UAST JSON，写出 `.py` 和 fidelity report。 |
| `uast/emitter-Python/package.json` | 声明本地 Node.js 包、`uast2py` 命令和 `npm test`。 |
| `uast/emitter-Python/test/python-emitter.test.js` | 新增的快速单测，检查确定性、赋值、容器、类方法中 `self` 的恢复，以及未知节点必须失败。 |
| `uast/emitter-Python/README_ZH.md` | 中文使用说明、已覆盖范围和已知限制。 |

当前已实现常见的导入、赋值、调用、成员访问、二元/一元表达式、切片、列表/字典、元组、
函数、类、`self`、类型注解、`if`、`for`、`while`、`try/except/finally`、`raise`、
lambda、yield、`*args`/`**kwargs` 等 UAST 节点。

### 验证与说明代码

| 文件 | 作用 |
| --- | --- |
| `workstreams/dl-cross-language-research/scripts/verify_dl_emitter_phase1.py` | 批量执行 emitter，运行生成程序，重新调用旧 `uast4py`，比较运行结果和 canonical UAST，并记录耗时。 |
| `workstreams/dl-cross-language-research/docs/PythonEmitter与PyTorch验证.md` | 补充 emitter、PyTorch、UAST、`expected.json` 与回转验证之间的关系，以及“歧义”和“确定丢失”的区别。 |
| `workstreams/dl-cross-language-research/docs/PyTorch-Phase1回转验证.md` | 本文档。 |

### 测试运行时自动生成的文件

这些文件在 `workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/DLxxx_*` 下，目录已被 Git 忽略，因此不会把大量
中间产物提交到仓库：

| 文件 | 来源和用途 |
| --- | --- |
| `source.py` | Phase 1 PyTorch 测试小程序。 |
| `source.uast.json` | 旧 `uast4py` 对 `source.py` 的解析结果；这是 emitter 的唯一业务输入。 |
| `expected.json` | 原始 `source.py` 在固定 CPU、固定随机种子下的运行结果。 |
| `roundtrip.py` | emitter 生成的 Python 源码。 |
| `roundtrip.uast.json` | 对 `roundtrip.py` 再次解析得到的 UAST。 |
| `fidelity-report.json` | emitter 对本例是否存在 UAST 歧义或确认损失的报告。 |
| `phase1-emitter-summary.json` | 20 个样例的汇总结果和计时。 |

## 3. 用了什么测试数据

测试数据不是从 PyTorch 官方仓库直接复制的一组大测试，而是本项目准备的、调用官方 PyTorch
API 的 20 个短小且可控的 Phase 1 种子程序。这样能让“源码—UAST—源码”的失败原因保持清晰。

样例计划在 `workstreams/dl-cross-language-research/fixtures/dl-uast-seed/manifest.json` 中：固定 CPU、随机种子 `20260911`，覆盖：

- Tensor 创建：`tensor`、`zeros`、`ones`、`arange`；
- shape 操作：`reshape`、转置、`unsqueeze/squeeze`、拼接、stack、切片索引；
- 基本数学：同形状/广播加法、减法、乘法、除法、二维矩阵乘；
- 归约和激活：`sum`、`mean`、ReLU、softmax。

这些样例首先是 emitter 的功能与语义回转集，不是 YASA 漏洞规则靶场，也不是用来证明
Python parser 新旧版本等价的完整基线。以后替换 parser 时，必须在同一批源码上分别生成
`UAST_old` 与 `UAST_new`，先直接比较两份 canonical UAST，再把它们分别交给同一个 emitter。

## 4. 实测结果

执行命令：

```bash
workstreams/dl-cross-language-research/.venv/bin/python \
  workstreams/dl-cross-language-research/scripts/verify_dl_emitter_phase1.py \
  --python workstreams/dl-cross-language-research/.venv/bin/python \
  --binary runtime/uast-v0.2.18/uast4py-linux-amd64
```

结果如下：

| 项目 | 结果 |
| --- | --- |
| Phase 1 样例数 | 20 |
| 成功生成 `roundtrip.py` | 20 / 20 |
| 运行结果一致 | 20 / 20 |
| canonical UAST 一致 | 20 / 20 |
| 两项均通过 | 20 / 20 |
| fidelity report：canonical | 4 |
| fidelity report：ambiguous | 16 |
| fidelity report：lossy | 0 |
| 20 次 emitter 总耗时 | 0.476 秒（含 20 次 Node.js 进程启动） |
| 20 次 PyTorch 执行总耗时 | 21.225 秒 |
| 20 次重新解析总耗时 | 7.708 秒 |

此外，单独用一个更广的 Python smoke 程序验证了类、方法 `self`、`int` 注解、
`*args/**kwargs`、循环、异常、切片和 `raise`；生成源码可通过 Python 语法编译，且
重新解析后的 canonical UAST 一致。

## 5. 检测到的局限：现有 UAST 的信息缺失与当前 emitter 覆盖范围

### 5.1 容器歧义

当前 Python parser 会把列表、集合和字典统一编码成 `ObjectExpression`：

```python
[]        # 空列表
{}        # 空字典
[1, 2]    # 列表
{1, 2}    # 集合
{0: 1, 1: 2}  # 连续整数键字典
```

其中部分写法在 UAST 中没有足够字段区分。emitter 因此只能使用确定性规则：

- 空容器默认生成 `{}`；如果同一变量后续调用 `append`、`extend` 或 `insert`，则推断为 `[]`；
- 连续整数键的非空 `ObjectExpression` 默认生成列表；
- 无法保证唯一正确时，在 `ambiguities` 写入
  `empty-container-ambiguity` 或 `indexed-container-ambiguity`。

所以 16 个样例虽然“运行结果一致且 UAST 回转一致”，仍然被诚实标记为 `ambiguous`，而不是
直接宣称无损。这正是运行行为验证不能省略的原因。

### 5.2 类型注解歧义

旧 Python parser 的 `PrimitiveType(kind=number)` 无法区分原始注解是 `int` 还是 `float`。
emitter 固定输出 `float`，并记录 `numeric-type-ambiguity`。重新解析后的 UAST 可以一致，但
作者原本写的类型文本未必能恢复。

### 5.3 parser 已降级的 Python 结构

以下结构在旧 parser 中会被展开、降级或部分忽略，UAST 不是原始 Python 语法树：

- `with` / `async with`；
- 列表、字典、集合、生成器推导式；
- `global`、`nonlocal`；
- f-string 的格式化细节；
- 注释、文档字符串、空白排版；
- 一些 `match` 模式和异步语义（例如 parser 对 `await` 的标记不足）。

对这类输入，emitter 要么把已扁平的 UAST 尽力生成成连续代码并在 `losses` 报告，要么对没有
可靠映射的节点 fail-closed。它不会假装恢复了原程序。

## 6. 这件事的当前边界

现在完成的是“Python UAST 逆向生成和 Phase 1 回转验证工具链”，不是把所有 Python 语法都
证明为完整支持，更不是新 Python parser 的替换工作。下一步可以按 Phase 2 的 30 个深度学习
样例扩展覆盖，再在新 Node.js Python parser 出现后，运行旧/新 parser 的直接 UAST diff、
emitter round-trip、运行行为和 YASA finding 四层回归。
