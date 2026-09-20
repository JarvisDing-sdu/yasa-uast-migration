# 五项验收与 PyTorch 106/122 UAST 差异说明

> 日期：2026-09-17。范围：Python parser 从旧 external `uast4py` 迁移到 Node.js + Tree-sitter。

## 核心数字

```text
真实 PyTorch 文件：122
旧 uast4py 可解析：122 / 122
新 Tree-sitter 可解析：122 / 122
old/new 语义 UAST 一致：106 / 122
存在差异：16 / 122，全部已完成源码级分类
```

因此：

```text
106 / 122 不是解析成功数。
122 / 122 才是解析成功数。
```

106/122 是 b「大项目 AST 解析与还原」中，新旧 parser UAST 对照的核心指标；它也帮助 a
发现并补充 parser 单测。它不等于 c、d 的 finding 数量，更不属于 e 的性能指标。

比较规则会忽略 `loc/sourcefile`，并把 JSON 的 float 书写 `1.0` 与 `1` 归一化；节点种类、
调用、变量、控制流、表达式和类型结构都参与比较。

## 测试流程

每个源码文件都走旧、新两条路线：

```text
source.py
  ├── old uast4py     → uast.old.json
  └── new Tree-sitter → uast.new.json
```

首先比较：

```text
semanticCanonical(UAST_old)
        与
semanticCanonical(UAST_new)
```

然后才验证 emitter：

```text
UAST_old/new → PythonEmitter → source.old/new.py → new parser → roundtrip UAST
```

批量脚本：

```text
workstreams/yasa-python-migration/scripts/verify_old_new_emitter_corpus.py
```

汇总产物：

```text
workstreams/dl-cross-language-research/artifacts/
└── pytorch-upstream-old-new-emitter/summary.json
```

## 当前 16 个差异

| 类别 | 文件数 | 结论 |
| --- | ---: | --- |
| 临时变量 alpha-equivalence | 7 | 仅 `__tmpN__` 编号不同，按出现顺序重编号后树相等 |
| 多层 comprehension lowering | 2 | 旧 parser 降级有嵌套/作用域问题；新 parser 更准确 |
| Tuple / Sequence | 2 | 新 parser 保留 tuple；旧 parser 用通用 Sequence |
| PEP 604 Union 类型 | 2 | 新 parser 保留嵌套 union 组合；旧 parser 摊平 |
| `self` 合成声明 | 3 | 旧 parser 漏掉类方法 self，或误判顶层普通参数 self |
| 未修复的新 parser bug | 0 | 无 |

### 多层 comprehension 的真实例子

```python
# test/test_nn.py:11177
[t if isinstance(t, torch.Tensor) else tt for t in out for tt in t]

# torch/nn/modules/utils.py:32
(x for x in reversed(t) for _ in range(n))
```

两个 `for` 应该嵌套。旧 visitor 将两个 `RangeStatement` 并列放进 `Sequence`；新 visitor
把第二层放在第一层 body 中，符合 Python 语义。

### Tuple 的真实例子

```python
# test/test_torch.py:866
t_all_true_but_one[(..., *idx)] = False

# test/test_torch.py:9837
t0[()] = 1

# _building.py:290
constant_farm[(arg, dtype)] = constant_value
```

旧 parser 用 `Sequence` 表示 tuple；新 parser 使用：

```text
TupleExpression(elements, modifiable=false)
```

这属于新 parser 更准确地表达源码结构。

### Union 类型的真实例子

```python
# _input_observer.py:449
set[int | str] | bool | None

# _registration.py:58
Literal["cuda", "cpu"] | str | None
```

旧 parser 摊平 union 成员；新 parser 保留嵌套的 union 组合树，适合后续类型源码还原。

### `self` 的真实例子

```python
# 类方法：type_promotion.py:154
def __eq__(self, other: object, /) -> bool:

# 顶层函数：symbolic_opset13.py:309
def where(g, condition, self=None, other=None, _outputs=None):
```

旧 parser 对前者漏掉 synthetic self，对后者又误加 `ThisExpression`。新 parser 根据函数是否
位于 `ClassDefinition` 内判断，结果正确。

## 本轮已修复的真实新 parser bug

初始为 104/122、18 个差异。本轮修复后变为 106/122、16 个差异。

```python
# f-string 插值算术
f"... {len(args) + 1} were ..."
```

先前的新 visitor 实现曾错误把插值内部 `+` 展开到字符串拼接树，现已保留：

```text
"..." + (len(args) + 1) + " were ..."
```

另一个修复是：

```python
[*product(xs)]
```

现在正确生成：

```text
DereferenceExpression(CallExpression(product, [xs]))
```

## 与 a–e 的关系

| 任务 | 当前验收点 | 106/122 的关系 |
| --- | --- | --- |
| a. UAST 单测回归 | parser 单测、19 类语义矩阵、旧 visitor 对照 | PyTorch 差异发现 bug 后补入单测 |
| b. 大项目解析与还原 | 122/122 可解析；20 小样例 20/20 运行/round-trip | **核心 parser 对照证据** |
| c. xAST 回归 | 旧/新扫描后比较 332 findings 与 trace | 16 个 UAST 差异不等于 finding 变化 |
| d. OWASP 检出 | 旧/新扫描后比较 190 findings 与评分 | 106/122 不直接参与该指标 |
| e. 性能 | 多轮耗时与 RSS 已记录 | 106/122 不属于性能指标 |

## 现场表述

推荐：

```text
新旧 parser 都能解析 122/122 个真实 PyTorch 文件。
其中 106 个文件的 UAST 在既定语义 canonical 规则下完全一致。
其余 16 个差异都已结合源码分类，没有遗留未解释的新 parser 语义 bug。
```

不要说：

```text
只有 106 个文件解析成功。
```

也不要说：

```text
122 个真实 PyTorch 文件全部无损还原。
```

47 个 emitter fail-closed 文件来自旧 UAST 对 generator/comprehension 的高级语义边界丢失，
属于 b 项发现的信息缺失，不是新 parser 无法解析。

## 详细材料

- `PyTorch真实源码-解析与还原.md`
- `PyTorch旧新UAST差异分类.md`
- `Python-UAST双侧还原-小样例.md`
- `Python解析器迁移-现场验收手册.md`
