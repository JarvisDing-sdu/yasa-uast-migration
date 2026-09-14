# PythonEmitter、UAST 与 PyTorch 验证关系说明

> 目标：解释 Python UAST → Python 源码如何验证，以及 PyTorch 样例、UAST JSON、expected.json 和 emitter 分别负责什么。

## 1. 最重要的结论

PythonEmitter 的严格输入只有：

```text
Python UAST JSON
```

它不读取：

```text
原始 source.py
expected.json
PyTorch 运行结果
loc.sourcefile 对应的原始文件文本
```

PyTorch 输出不是 emitter 的输入，而是验证 emitter 是否保持功能的标准答案。

## 2. 参与对象

| 对象 | 它是什么 | 作用 |
| --- | --- | --- |
| `source.py` | 原始、可运行的 PyTorch 小程序 | 被解析的源程序，也是功能参考实现 |
| `expected.json` | 原始程序运行后的结果 | 保存 Tensor 数值、shape、dtype、device，作为运行时 oracle |
| `source.uast.json` | parser 从 `source.py` 生成的 UAST | PythonEmitter 的严格输入 |
| PythonEmitter | 确定性的 UAST → Python 源码工具 | 输出规范 Python 源码和信息损失报告 |
| `roundtrip.py` | PythonEmitter 输出的源码 | 用来重新解析、重新运行和比较 |
| `roundtrip.uast.json` | 对 `roundtrip.py` 再解析的 UAST | 用于 emitter 自身 round-trip 验证 |

## 3. 完整数据流

```text
                         ┌─────────────────────┐
                         │  原始 source.py      │
                         │  PyTorch 小样例      │
                         └─────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
          Python + torch 执行                 Python parser
                    │                             │
                    ▼                             ▼
             expected.json                 source.uast.json
             数值/shape/dtype                    │
                    │                             ▼
                    │                       PythonEmitter
                    │                             │
                    │                             ▼
                    │                       roundtrip.py
                    │                             │
                    │              ┌──────────────┴──────────────┐
                    │              │                             │
                    │              ▼                             ▼
                    │       Python + torch 执行             Python parser
                    │              │                             │
                    ▼              ▼                             ▼
              输出数值比较     actual result              roundtrip.uast.json
                    │              │                             │
                    └──────────────┴─────────────┬───────────────┘
                                                   ▼
                                      运行语义 / UAST / loss report 验证
```

严格模式下，emitter 只处于：

```text
source.uast.json → PythonEmitter → roundtrip.py
```

这避免 emitter 从原始源码或正确结果中“偷看答案”。

## 4. torch 调用和 UAST 的关系

例如原始源码：

```python
result = torch.relu(torch.matmul(a, b))
```

Python parser 不需要理解矩阵乘法或 ReLU 的数学含义。它只需要理解 Python 语法结构：

```text
AssignmentExpression
├── left: Identifier(result)
└── right: CallExpression
    ├── callee: MemberAccess(torch, relu)
    └── arguments:
        └── CallExpression
            ├── callee: MemberAccess(torch, matmul)
            └── arguments: [Identifier(a), Identifier(b)]
```

PythonEmitter 根据这些普通节点重新输出：

```python
result = torch.relu(torch.matmul(a, b))
```

因此：

```text
parser/emitter 负责 Python 程序结构；
torch 软件包负责真正执行矩阵乘法和 ReLU；
DL Semantic Profile 负责后续跨语言时理解 Tensor、shape、dtype、device 等领域语义。
```

## 5. PythonEmitter 是什么

PythonEmitter 是 Node.js/TypeScript 中的一个源码生成模块，不是大模型。

当前实现位于：

```text
uast/emitter-Python/
```

实现结构：

```text
PythonEmitter
├── validateCompileUnit
├── emitStatement
│   ├── FunctionDefinition
│   ├── AssignmentExpression
│   ├── IfStatement
│   ├── RangeStatement
│   ├── ReturnStatement
│   └── ImportExpression
├── emitExpression
│   ├── Identifier
│   ├── Literal
│   ├── CallExpression
│   ├── MemberAccess
│   ├── BinaryExpression
│   └── UnaryExpression
├── indentation / precedence policy
└── fidelity/loss reporter
```

命令行入口为 `uast/emitter-Python/src/cli.js`，批量闭环验证入口为
`workstreams/dl-cross-language-research/scripts/verify_dl_emitter_phase1.py`。

例如：

```text
MemberAccess(torch, relu)
  → torch.relu

CallExpression(callee, [x])
  → emit(callee) + "(" + emit(x) + ")"

AssignmentExpression(x, "=", 1)
  → x = 1
```

有限的 UAST 节点类型可以递归组合出无限多程序。

## 6. 什么叫确定性 emitter

确定性意味着：

```text
同一份 UAST JSON
+ 同一版本 emitter
+ 同一配置
= 永远输出相同 Python 源码
```

它必须：

```text
只读取 UAST；
不调用 LLM；
不随机选择写法；
不读取原始 source.py；
不根据 sourcefile 或位置回填原文本；
不因为机器、临时目录不同而改变输出。
```

例如，若 UAST 已把 `x += 1` 归一化为 `x = x + 1`，emitter 固定输出：

```python
x = x + 1
```

目标是生成规范源码，不是恢复作者的原始排版。

## 7. UAST 节点数量

需要区分：

```text
UAST 节点类型数量：
某个 specification 版本中固定，例如 Identifier、Literal、CallExpression。

某个程序的节点实例数量：
不固定，小程序可能十几个，大程序可能数万个。

节点组合方式：
无限。
```

因此 emitter 不会为每种完整程序写一个规则，而是为每种节点写递归规则。

## 8. emitter 是否能处理任何 UAST

不能，也不应承诺。

PythonEmitter 只支持：

```text
Python parser 能产生
并已被列入 Python UAST 支持矩阵
且可以可靠投影回 Python 的节点子集。
```

Java、Go、PHP 的语言特有 UAST 节点不能要求 PythonEmitter 输出 Python。

对于 Python 中已经被降级或合成的节点，例如复杂推导式、f-string、dataclass 合成构造函数，emitter 必须给出明确结果：

```text
Exact
Canonical
Approximate
Unsupported
Synthetic
```

不支持节点必须 fail-closed：

```text
报告 UnsupportedNode、节点类型、位置和原因；
不得静默输出空字符串；
不得把 case 判为旧新 parser 等价。
```

还需要区分“确定丢失”和“无法唯一判断”：

```text
losses：已经确认不能用等价 Python 结构表达；
ambiguities：UAST 对应多种 Python 写法，emitter 只能按固定规则选择一种。
```

当前 Python UAST 的一个实际歧义是，`list`、`set` 和 `dict` 都使用
`ObjectExpression`。空列表和空字典的语义字段完全相同；非空列表、集合与键为
`0..n-1` 的字典也会形成相同节点。emitter 对这种节点固定选择列表或字典，同时在
fidelity report 中记录 `empty-container-ambiguity` 或
`indexed-container-ambiguity`。因此，round-trip UAST 一致并不自动证明容器运行语义一致，
还必须执行程序。

## 9. 如何证明 emitter 有效

Emitter 不是 parser 正确性的唯一裁判，必须独立验证。

### 第一层：直接 UAST 比较

```text
canonical(UAST_old) 与 canonical(UAST_new)
```

这是 parser 迁移的首要判据。移除 `sourcefile`、`parent`、`nodehash` 等环境噪声，但保留节点类型、字段、顺序、运算符、参数和关键 metadata。

### 第二层：emitter 自身 round-trip

```text
UAST A
  → PythonEmitter
  → Python R
  → Python parser
  → UAST B
  → canonical(A) == canonical(B)
```

先用人工构造的每种节点样例验证 emitter，再用于 parser 对比。

### 第三层：运行行为

```text
source.py 的 PyTorch 输出
与 roundtrip.py 的 PyTorch 输出比较：

数值
shape
dtype
device
NaN/Inf
预期异常
```

### 第四层：静态分析行为

对原始源码和还原源码运行 YASA，比较：

```text
finding
source/sink
污点链
SARIF 位置
解析失败
```

## 10. 最终判定

| 情况 | 判定 |
| --- | --- |
| 旧新 UAST 直接一致，生成源码可解析且运行一致 | 高可信通过 |
| UAST 差异属于已批准 canonical 化 | 通过，但报告差异 |
| emitter 不支持某节点 | 未验证，不能宣称通过 |
| UAST、运行结果或 YASA finding 不同 | 需要排查 parser/emitter/语义问题 |

最重要的原则：

> 直接 UAST diff 是首要证据；emitter round-trip 是第二证据；PyTorch 运行结果是第三证据。生成源码相同不能单独证明两份 UAST 相同。
