# b 项阶段二：PyTorch 上游真实源码解析与还原

## 目的与输入

本阶段用 PyTorch 上游稀疏克隆中的 122 个真实 Python 文件，验证新 Tree-sitter parser 与
`PythonEmitter` 在大于小型 fixture 的真实源码上的行为。它不尝试运行整个 PyTorch 框架；
PyTorch 源码依赖 C++/CUDA 构建产物，b 项此处验证的是解析、UAST、还原源码和重新解析。

输入位于 Git 忽略的：

```text
workstreams/dl-cross-language-research/benchmarks/pytorch-upstream/
```

覆盖稀疏克隆的 `torch/nn/modules`、`torch/onnx` 以及两个大型测试文件。

## 流程

对每个 `.py` 文件运行：

```text
source.py
  ├─ old external uast4py → uast.old.json → emitter → source.old.py
  └─ new Tree-sitter      → uast.new.json → emitter → source.new.py

source.old.py → new Tree-sitter → uast.old.roundtrip.new-parser.json
source.new.py → new Tree-sitter → uast.new.roundtrip.new-parser.json
```

比较器移除 `loc/sourcefile`，并对 `literalType=float`、`literalType=number` 的 JSON 数字
书写差异进行语义规范化。严格差异仍保存在每个 artifact 中，不会被删除。

脚本：

```text
workstreams/yasa-python-migration/scripts/verify_old_new_emitter_corpus.py
```

复现：

```bash
python3 workstreams/yasa-python-migration/scripts/verify_old_new_emitter_corpus.py \
  --source-dir workstreams/dl-cross-language-research/benchmarks/pytorch-upstream \
  --artifact-dir workstreams/dl-cross-language-research/artifacts/pytorch-upstream-old-new-emitter \
  --old-binary runtime/uast-v0.2.18/uast4py-linux-amd64
```

逐文件 UAST、还原源码、fidelity report 和 `summary.json` 都在 Git 忽略的 artifact 目录中。

## 2026-09-17 结果

| 指标 | 结果 |
| --- | ---: |
| 真实 Python 文件 | 122 |
| old binary 成功解析 | 122 / 122 |
| new Tree-sitter 成功解析 | 122 / 122 |
| old/new 语义 UAST 一致 | 106 / 122 |
| old UAST 成功 emitter | 75 / 122 |
| new UAST 成功 emitter | 75 / 122 |
| old emitter 输出经新 parser 语义 round-trip | 39 / 122 |
| new emitter 输出经新 parser 语义 round-trip | 40 / 122 |
| 双侧 UAST 一致且双侧 round-trip 通过 | 39 / 122 |

这是一份真实失败也保留的报告，不是只挑选可通过文件的结果。

## 大整数精度问题与修复

本次语料发现：

```python
INT64_MAX = 9223372036854775807
```

曾被新 parser 的 JavaScript `Number(text)` 静默变成：

```text
9223372036854776000
```

原因是 JavaScript `Number` 只能精确表示到 `2^53 - 1`，而 Python `int` 是任意精度。
修复后，超过安全范围的整数保留为：

```json
{ "value": "9223372036854775807", "literalType": "number" }
```

emitter 将这种 `literalType=number` 的纯数字字符串原样输出为 Python 数字 token。新增
`INT64_MAX/INT64_MIN` parser 单测与 emitter 单测后，完整 parser 测试 19/19 通过，
PyTorch 语义 UAST 一致数从 79 提升到 80。

后续针对相邻 f-string 的兼容修复，将 `concatenated_string` 中相邻的 string Literal
按旧 Visitor 行为合并，保持插值顺序不变。例如：

```python
f"prefix=" f"{value}" f", suffix={other}"
```

不再因旧/new 的 `BinaryExpression('+')` 结合方式不同而产生差异。修复后 old/new
语义 UAST 一致数从 80 提升到 **104 / 122**。后续差异分类又发现并修复了 f-string
插值加法边界与 list-splat call 绑定问题；最新全量结果为 **106 / 122**，parser 测试通过。

## 已知失败分类

### 1. 47 个 emitter fail-closed：无初始化 `VariableDeclaration`

这类节点主要来自 generator/list/dict comprehension。旧 Python UAST 会把：

```python
target(x for x in xs)
```

降级为类似：

```text
Sequence(
  VariableDeclaration(__tmp1__),
  RangeStatement(...),
  Identifier(__tmp1__)
)
```

当该低级 Sequence 位于调用参数或表达式内部时，原始“这是 generator expression”的边界已
不再存在。emitter 如果强行输出 `__tmp1__`，会生成未定义变量或改变执行顺序。因此当前选择
fail-closed，而不是生成看似成功但语义错误的 Python。

这是旧 UAST 表达对源码逆向不足的证据，也是 b 项要求“还原后检查信息缺失”的实际发现。

### 2. 已修复的 emitter 生成语法错误

初次完整回归发现 3 个 emitter 输出无法被新 parser 再解析；现已补齐并重新全量回归：

| 原错误 | 修复 |
| --- | --- |
| `except as null:` | 旧 UAST 用 `Literal(value=null, literalType='string')` 表示裸 `except:`；emitter 现在正确输出 `except:`。 |
| `x[(:, :, :, :limit)]` | 旧 UAST 用 `Sequence(SliceExpression, ...)` 表示多维下标；emitter 现在正确输出 `x[:, :, :, :limit]`。 |
| 类型成员/字面量无法生成 | emitter 现在支持 `torch.dtype`、前向字符串/字面量类型和 PEP 604 类型表达式。 |

修复后不再存在 `old-reparse` 语法失败；剩余 47 个失败均为下文的 fail-closed
`VariableDeclaration` 情形。

### 3. old/new UAST 剩余 16 个已分类差异

最新 106/122 严格一致。剩余 16 个已逐文件对照源码并完成分类：临时变量编号 7、旧
comprehension 错误降级 2、Tuple/Sequence 精确建模 2、PEP 604 Union 类型建模 2、旧
parser 对 `self` 的误判/漏判 3。详见
[PyTorch旧新UAST差异分类](PyTorch旧新UAST差异分类.md)。

## 性能观察（非 e 项最终结论）

本脚本为每个文件独立启动 old binary 和 Node.js 导出器，主要用于 b 项功能验证：

| 阶段 | 总耗时 |
| --- | ---: |
| old binary parse | 84.49 s |
| new parser export | 13.20 s |

这提示新 parser 在该语料上明显更快，但不能替代 e 项：尚未统一 `/usr/bin/time -v`、
worker 生命周期和完整 Engine 分析口径。

## b 项当前结论

阶段一的 20 个可执行 PyTorch 小样例已实现 old/new 双侧 UAST、emitter、运行行为和
round-trip 的 20/20 通过。阶段二证明新 parser 对 122 个真实文件可全量解析，并量化了
emitter 的成功率与 UAST 的逆向信息缺失。

因此可以说 b 已完成“真实大项目解析与还原评估”，但不能声称“122 个文件全部可无损还原”。
后续工作是对 47 个推导式/生成器降级 case 设计更高层的 UAST 表达或明确列为不可逆限制，
剩余 16 个严格 JSON 差异已有逐项证据，不应通过丢弃新 parser 的准确信息强行归零。
