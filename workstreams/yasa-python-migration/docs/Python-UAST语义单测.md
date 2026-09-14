# Python UAST 语义矩阵单测

## 目的

初始新 Python parser 测试有 16 个 Node.js 测试场景，但单纯看“16”不能说明覆盖了多少
Python 语义。本次新增一套 19 case 的语义矩阵：新 Tree-sitter parser 必须先满足每个
语义单元的 UAST 节点要求，再与旧 Python `ast` Visitor 的输出比较。

测试代码位于：

```text
uast/parser-Python/tests/semantic-matrix.test.ts
```

大整数精度回归补在：

```text
uast/parser-Python/tests/parser.test.ts
```

旧 oracle 位于：

```text
uast/parser-Python/tests/legacy.py
uast/parser-Python/uast/visitor.py
```

oracle 仅在测试中被 Node.js 启动。生产 Engine 不会调用 Python oracle 或旧 external
`uast4py` binary。

## 覆盖矩阵

| 语义单元 | 语义矩阵 case |
| --- | --- |
| 字面量与容器 | `None`、布尔值、bytes、list、dict、tuple、set |
| 赋值 | 链式赋值、解构赋值、增量赋值 |
| 导入 | `import`、相对 `from import`、别名 |
| 函数 | 装饰器、位置专用参数、默认值、类型注解、`*args`、关键字专用参数、`**kwargs`、返回类型 |
| 表达式函数 | lambda、条件表达式、walrus `:=` |
| 类 | 继承、构造器、`self`、成员访问 |
| 控制流 | `if/elif/else`、`for`、`while`、`break`、`continue` |
| 异常与资源 | `try/except/finally`、`raise`、`with` |
| 调用 | 关键字参数、`*args` 展开、`**kwargs` 展开 |
| 访问与运算符 | 属性、索引、切片、算术、比较、布尔链、`not in`、`is not` |
| 推导式 | list、dict、generator comprehension |
| 生成器与异步 | `yield`、`yield from`、`async def`、`async for`、`async with` |
| 模式匹配 | sequence pattern、mapping pattern、wildcard、guard |
| dataclass 与字符串 | dataclass 构造器合成、f-string |

这不是“Python 所有语法已经穷尽”的声明。它是可维护的核心语义回归矩阵：新增 bug 时应向
该文件增加一个独立、最小的 case，而不是只依赖大项目扫描结果。

## 新旧对照规则

19 个 case 分三类：

| 类型 | 数量 | 验收规则 |
| --- | ---: | --- |
| 严格兼容 | 16 | 新旧 UAST 的全部字段（含 `loc`、`_meta`）必须一致。 |
| 已知位置差 | 2 | 去掉 `loc` 后必须严格一致。 |
| 已知旧 parser 缺口 | 1 | 新 parser 必须保留新语义，不能为了与旧 parser 一致而丢弃。 |

两个位置差分别是：

1. 布尔链的中间 `BinaryExpression`：旧 Visitor 合成节点时位置为空，新 Visitor 给出完整
   span；操作符和子节点一致。
2. f-string 文本片段：新旧 Visitor 对部分片段的列范围不同；去掉位置后结构一致。

一个旧 parser 缺口是 `match` guard：

```python
case [head, *tail] if head > 0:
```

旧 Visitor 丢弃 guard，直接保留 case body；新 Tree-sitter Visitor 将 guard 保留为
`CaseClause.body` 内的 `IfStatement`。这是语义补全，测试明确要求两者不相等，防止未来
为了“旧新一致”而把新语义删除。

## 复现命令

先安装/构建新 parser：

```bash
cd uast/parser-Python
npm ci --ignore-scripts
npm run build
```

只验证新 parser 自身的 19 case：

```bash
node --import tsx tests/semantic-matrix.test.ts
```

使用旧 Python Visitor 进行完整新旧对照：

```bash
PYTHON_UAST_ORACLE="$PWD/.venv/bin/python" npm test
```

2026-09-13 本机结果：

```text
原有 parser 测试 + 语义矩阵 + 大整数与相邻 f-string 回归：20 / 20 passed
新增语义 matrix：19 个 case 全部通过其对应验收规则
```

本机 oracle 为 CPython 3.10.12。Python 3.11 的 `except*`、Python 3.14 template string
等版本特定语法，仍需使用相应版本的 old oracle 或按明确“不支持”规则单独测试。
