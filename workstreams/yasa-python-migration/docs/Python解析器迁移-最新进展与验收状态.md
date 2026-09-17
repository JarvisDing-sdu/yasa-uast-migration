# Python 解析器迁移：最新进展与验收状态

> 最后更新：2026-09-17。本文是阅读入口；每个数字和命令仍以链接的专项报告为准。

## 当前结论

新 Python Tree-sitter parser 已经在 Node.js/Engine 生产路径中运行。它在 xAST 和 OWASP
回归中没有改变 finding 或污点 trace；真实 PyTorch 源码测试还发现并修复了大整数精度与
相邻 f-string UAST 兼容问题。

```text
旧：external uast4py binary → JSON 文件 → Engine
新：Node.js + Tree-sitter WASM → 内存 UAST → Engine
```

## a 到 e 状态

| 验收项 | 状态 | 当前证据 | 尚缺事项 |
| --- | --- | --- | --- |
| a. UAST 单测回归 | 基本完成 | parser 20/20；19 个通用语义 matrix case；606 xAST old/new 对照 | 分类少量 Python 版本和位置差异 |
| b. 大项目解析与还原 | 已完成评估，非 122/122 无损 | Phase 1 PyTorch 20/20 双侧运行/round-trip；真实 PyTorch 122/122 可解析，106/122 old/new 语义 UAST 一致；剩余 16 个全部分类 | 47 个 generator/comprehension 降级结构需 UAST 扩展或列为不可逆 |
| c. YASA xAST 回归 | 通过 | 606 文件、332 finding；规范化后完整 SARIF/codeFlow/threadFlow 一致 | 无 |
| d. OWASP Python 检出 | 通过 | 1,230 文件、190 finding、TP/FN/TN/FP 和完整 trace 一致 | Go 不在当前范围 |
| e. 性能 | 部分完成 | OWASP、新旧 parser export、PyTorch 语料均有时间观察 | 用同一 `/usr/bin/time -v` 和 worker 生命周期重测 peak RSS |

## 2026-09-14 最新修复

### 1. 大整数精度：真实 parser bug，已修

```python
INT64_MAX = 9223372036854775807
```

原先新 parser 通过 JavaScript `Number(text)` 变成 `9223372036854776000`。修复后，超过
JavaScript 安全整数范围的 Python integer 以原始数字文本保存，保持 `literalType="number"`，
emitter 再原样输出。新增 `INT64_MAX/INT64_MIN` 回归测试。

### 2. 相邻 f-string：旧 UAST canonical 兼容修复

相邻 f-string 的纯文本片段在旧 CPython Visitor 中会合并，新 Visitor 原先保留多个 Literal，
造成 `BinaryExpression('+')` 树形状差异。新 Visitor 现在只合并相邻 string Literal；后续
又修复了插值内部 `a + b` 被误展开的问题。另修复 `[*call(...)]` 的星号绑定。PyTorch 122
文件 old/new 语义 UAST 一致数最终由 80 提升到 106。

这不是 Tree-sitter 语法解析错误，而是新 Visitor 输出需遵循旧 UAST 的稳定规范形状。

### 3. emitter 还原修复

已修复 `None`、大整数、解构循环目标、类型成员访问、裸 `except:` 与多维切片。三个“生成
源码后无法重新解析”的真实 PyTorch case 已消除。剩余 47 个 fail-closed 是旧 UAST 把
generator/comprehension 降级为 `Sequence + __tmpN__ + RangeStatement` 后丢失表达式边界，
不能安全由 emitter 猜回原文。

## 关键证据文档

| 主题 | 文档 |
| --- | --- |
| 新 parser 架构、npm、WASM | [Node与WASM解析器说明](Node与WASM解析器说明.md) |
| 旧 parser 基线 | [Python-UAST旧基线](Python-UAST-旧基线.md) |
| 通用语义单测 | [Python-UAST语义单测](Python-UAST语义单测.md) |
| 小样例双侧还原 | [Python-UAST双侧还原-小样例](Python-UAST双侧还原-小样例.md) |
| PyTorch 真实源码评估 | [PyTorch真实源码-解析与还原](PyTorch真实源码-解析与还原.md) |
| PyTorch 剩余差异分类 | [PyTorch旧新UAST差异分类](PyTorch旧新UAST差异分类.md) |
| xAST finding/trace 对比 | [xAST-检出与性能对比](xAST-检出与性能对比.md) |
| OWASP 安全靶场回归 | [OWASP-Python-旧新回归](OWASP-Python-旧新回归.md) |

## 接下来

1. 完成 e：以相同命令、worker、`/usr/bin/time -v` 口径重测 xAST 和 OWASP 的 peak RSS；
2. 固定所有版本、命令与 artifact hash，形成最终验收记录；
3. parser 迁移收口后，再开始规则工坊。DL 跨语言研究已移入独立私有仓库。
