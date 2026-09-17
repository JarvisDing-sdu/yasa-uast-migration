# PyTorch 旧/新 Python UAST 差异分类

> 日期：2026-09-17  
> 范围：PyTorch 官方稀疏语料 122 个 `.py` 文件  
> 旧 parser：YASA-UAST v0.2.18 `uast4py-linux-amd64`  
> 新 parser：Node.js + Tree-sitter Python parser

## 结论

初始报告为 **104/122** 个文件 old/new 语义 UAST 严格一致，18 个文件存在差异。本轮逐项
对照原始源码后，发现并修复了两个新 parser 实现问题：

1. f-string 插值中的 `a + b` 被错误展开进外层字符串拼接树；
2. `[*product(xs)]` 的 `*` 被错误挂到 callee，而不是完整调用结果。

修复并全量重跑后：

| 指标 | 结果 |
| --- | ---: |
| old parser 成功解析 | 122 / 122 |
| new parser 成功解析 | 122 / 122 |
| old/new 严格语义 UAST 一致 | **106 / 122** |
| 仍有差异 | **16 / 122** |

剩余 16 个文件均已分类：7 个仅为临时变量编号，9 个是新 parser 更准确地保存原始源码
结构或旧 parser 的既有降级。没有遗留“已确认的新 parser 语义 bug”。这不代表 16 份 JSON
可直接判相等，而是说明每项差异已有源码依据和处置结论。

## 判定原则

旧 binary 是兼容基线，不是语义真理。分类时同时检查：

```text
原始 Python 源码
旧 UAST
新 UAST
旧/new visitor 的 lowering 实现
```

只有新 UAST 改变或丢失原始程序含义时才修改新 parser。旧 parser 漏信息时，不能为了
JSON 相等而让新 parser 重复旧错误。

## 已修复的新 parser bug

### 1. f-string 插值加法边界

涉及：

- `torch/nn/modules/conv.py:797-798`
- `torch/nn/modules/module.py:495`

例如：

```python
f"... {len(args) + 1} were ..."
```

旧 UAST 正确保留：

```text
"..." + (len(args) + 1) + " were ..."
```

新 parser 先前错误生成：

```text
"..." + len(args) + 1 + " were ..."
```

原因是相邻 f-string 兼容逻辑递归展开了所有 `BinaryExpression('+')`，无法区分“外层字符串
拼接”和“插值内部算术加法”。修复后只展开 visitor 自己创建的 f-string join 节点，插值
表达式保持一个整体。新增 `f"value={len(args) + 1}"` 回归测试。

### 2. 列表展开完整调用结果

涉及 `test/test_torch.py:6875-6880`：

```python
test_args = [*product(...)]
```

正确结构是：

```text
DereferenceExpression(
  CallExpression(product, ...)
)
```

新 parser 先前生成：

```text
CallExpression(
  DereferenceExpression(product), ...
)
```

修复后检测 Tree-sitter 把 `list_splat` 放在 call 的 function field 中的情形，将星号包在
完整 `CallExpression` 外。新增 `x = [*product(xs)]` 回归测试。

## 剩余 16 个文件分类

### A. 临时变量 alpha-equivalence：7 个

| 文件 |
| --- |
| `torch/nn/modules/activation.py` |
| `torch/nn/modules/transformer.py` |
| `torch/onnx/_internal/exporter/_dispatching.py` |
| `torch/onnx/_internal/exporter/_dynamic_shapes.py` |
| `torch/onnx/_internal/torchscript_exporter/symbolic_helper.py` |
| `torch/onnx/_internal/torchscript_exporter/utils.py` |
| `torch/onnx/ops/_symbolic_impl.py` |

差异仅为 `__tmp1__`、`__tmp2__` 等内部临时变量编号。分别按出现顺序重命名为统一编号后，
完整 canonical UAST 相等。临时变量不来自用户源码，不应靠修改 parser 强行匹配全文件的
计数历史；比较器可在专项报告中做 alpha-normalization，但普通 Identifier 不能被忽略。

### B. comprehension lowering：2 个，旧 parser 降级有误

| 文件 | 原始源码 |
| --- | --- |
| `test/test_nn.py:11177` | `[... for t in out for tt in t]` |
| `torch/nn/modules/utils.py:32` | `(x for x in reversed(t) for _ in range(n))` |

旧 visitor 将多个 `for` 对应的 `RangeStatement` 并列放入 `Sequence`，后一个循环引用前一个
循环变量时已经脱离其作用域。新 visitor 将第二层循环嵌入第一层循环 body，符合 Python
推导式的嵌套执行顺序。因此保留新结构，不向旧错误对齐。

### C. Tuple/Sequence 精确建模：2 个，新 parser 更准确

| 文件 | 代表源码 |
| --- | --- |
| `test/test_torch.py:866,919,9837` | `x[(..., *idx)]`、`t0[()]` |
| `torch/onnx/_internal/exporter/_building.py:290,697` | `dict[(arg, dtype)]` 等 tuple key |

旧 parser 用通用 `Sequence` 表示 tuple 下标或 tuple key；新 parser 使用
`TupleExpression(elements, modifiable=false)`，保留“这是 tuple”的语义。属于批准的 UAST
表示改进。`test_torch.py` 中同文件的 `[*product(...)]` 真 bug 已单独修复。

### D. PEP 604 Union 类型建模：2 个，新 parser 保留组合结构

| 文件 | 代表源码 |
| --- | --- |
| `torch/onnx/_internal/exporter/_input_observer.py:449` | `set[int | str] | bool | None` |
| `torch/onnx/_internal/exporter/_registration.py:58` | `Literal[...] | str | None` |

旧 parser 把 union 成员摊平成外层 typeArguments；新 parser 使用嵌套的 `Union` DynamicType
表达 `|` 组合。两者对 Union 的集合含义接近，但新结构更忠实于原始类型表达式树。此项归为
类型 canonical 差异，不是运行语义回归。

### E. `self` 合成声明：3 个，旧 parser 误判或漏判

| 文件 | 结论 |
| --- | --- |
| `torch/onnx/_internal/fx/passes/type_promotion.py` | `__eq__(self, other, /)` 是类方法；旧 parser 漏掉 synthetic self，新 parser 正确保留 |
| `torch/onnx/_internal/torchscript_exporter/symbolic_opset13.py` | `where(g, condition, self, ...)` 是顶层函数；旧 parser 因参数名 `self` 错加 `ThisExpression`，新 parser 正确不加 |
| `torch/onnx/_internal/torchscript_exporter/symbolic_opset9.py` | 同上，顶层 `where()` 的 `self` 只是普通参数 |

此类差异说明“参数名叫 self”不足以判断实例方法；必须结合是否位于 ClassDefinition 内。

## 回归命令

```bash
cd uast/parser-Python
npm run build
npm test

cd ../..
python3 workstreams/yasa-python-migration/scripts/verify_old_new_emitter_corpus.py \
  --source-dir workstreams/dl-cross-language-research/benchmarks/pytorch-upstream \
  --artifact-dir workstreams/dl-cross-language-research/artifacts/pytorch-upstream-old-new-emitter \
  --old-binary runtime/uast-v0.2.18/uast4py-linux-amd64
```

最新全量结果：old/new 均 122/122 解析成功，严格语义 UAST 106/122 一致；emitter 与
round-trip 数量仍为 old 75/122、new 75/122、old round-trip 39/122、new round-trip
40/122。后几项未因本轮 parser 修复下降。

## 验收结论

原“剩余 18 个差异待分类”现已关闭：

```text
18 个初始差异文件
├── 发现并修复新 parser bug：3 个源码点（涉及 3 个文件）
│   ├── 2 个 f-string 文件因此转为严格一致
│   └── 1 个 list-splat 文件仍因 tuple canonical 差异保留在剩余集合
└── 当前 16 个差异文件
    ├── 临时变量编号：7
    ├── 旧 comprehension 降级：2
    ├── Tuple/Sequence：2
    ├── Union 类型建模：2
    └── 旧 self 误判/漏判：3
```

不建议为了达到 122/122 字节/JSON 相等而回退新 parser 的更准确信息。最终验收应同时报告
“106/122 严格相等”和“16/16 差异已有证据分类”。
