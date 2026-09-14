# Python UAST 确定性源码生成器

这个目录实现 `PythonEmitter`：输入 YASA UAST v0.2.18 的 Python
`CompileUnit` JSON，确定性地输出 Python 源码。它是 UAST 的逆向生成器，
不是 Python parser，也不读取原始源码或程序运行结果。

## 使用

```bash
node src/cli.js \
  --input source.uast.json \
  --output roundtrip.py \
  --report fidelity-report.json
```

也可以作为 CommonJS 模块使用：

```javascript
const { PythonEmitter } = require('./src/python-emitter')
const { source, report } = new PythonEmitter().emit(uast)
```

输出遵循以下约束：

- 相同 UAST 必须得到字节级相同的源码；
- emitter 只依赖 UAST，测试答案不会泄漏进生成过程；
- 未注册的节点抛出 `UnsupportedNodeError`，不静默删除；
- UAST 已经丢失、但仍能生成近似代码的情况写入 fidelity report；其中
  `ambiguities` 表示存在多种合法还原，`losses` 表示确认无法等价表达；
- 源码位置 `loc` 不参与生成。

当前已覆盖首批 PyTorch 样例使用的全部 20 种节点，并实现函数、类、类型注解、
条件、循环、异常、导入、调用、切片、容器、lambda、yield 和展开参数等常用节点。
Python parser 本身会把 `with`、推导式、`global/nonlocal` 等结构降级或展开，
原 UAST 不再保留足够信息时，任何 emitter 都无法唯一还原原文；这类输入必须依据
fidelity report 和运行行为判断，不能宣称“原文还原”。

一个具体限制是：当前 UAST 会把 Python 的列表、集合和字典都编码为
`ObjectExpression`。空列表与空字典完全相同；列表又与键为 `0..n-1` 的字典、
集合采用相同节点形状。emitter 使用确定性规则选择列表或字典，并明确报告歧义。

## 验证

目录内快速单测：

```bash
npm test
```

项目根目录的真实闭环测试：

```bash
workstreams/dl-cross-language-research/.venv/bin/python \
  workstreams/dl-cross-language-research/scripts/verify_dl_emitter_phase1.py \
  --python workstreams/dl-cross-language-research/.venv/bin/python \
  --binary runtime/uast-v0.2.18/uast4py-linux-amd64
```

闭环同时检查：

1. `source.uast.json -> roundtrip.py` 后的 PyTorch 运行结果；
2. `roundtrip.py -> roundtrip.uast.json` 后的 canonical UAST；
3. 每个样例的 fidelity report。

canonical 比较只去掉行列号和源文件路径，语义节点字段不会被忽略。
