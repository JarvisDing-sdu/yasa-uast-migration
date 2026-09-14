# 深度学习 UAST 种子验证集

本目录定义 Python/PyTorch → UAST → Python 及未来跨语言生成的首批 50 个确定性测试 case。

它的用途是验证，不是训练大模型：

```text
源码能否解析为 UAST
UAST 能否逆向生成源码
生成源码能否重新解析
Tensor 输出、shape、dtype 是否一致
```

`manifest.json` 是 case 的规范。每个 case 后续应生成：

```text
source.py                 PyTorch 参考源码
input.json                固定输入和随机种子
expected.json             输出、shape、dtype 或预期异常
source.uast.json          旧 parser UAST
roundtrip.py              PythonEmitter 输出
roundtrip.uast.json       再解析 UAST
fidelity-report.json      信息损失报告
```

执行顺序：

1. 先完成 `phase: 1` 的 20 个基础 case；
2. 验证 UAST round-trip 与 CPU 数值输出；
3. 再实现 `phase: 2` 的层、模型、梯度和训练 case；
4. 50 个 case 全部通过后，扩展到 100+ case 和跨语言后端；
5. 训练数据应来自大量验证通过的 source/UAST/target-source 三元组，不能把这 50 个 case 当成足够的微调数据。

统一运行约束：

```text
device = cpu
seed = 20260911
默认 dtype = float32
推理 case 使用 eval/inference 语义
比较输出值、shape、dtype、NaN/Inf 和预期异常
```

## 当前基线状态

2026-09-11 已使用本地 CPU PyTorch `2.14.0+cpu` 生成并执行 Phase 1 的 20 个 case：

```text
DL001-DL020 运行：20 passed, 0 failed
DL001-DL020 旧 uast4py 解析：20 passed, 0 failed
```

生成产物位于被 Git 忽略的：

```text
workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/
```

复跑命令：

```bash
workstreams/dl-cross-language-research/.venv/bin/python \
  workstreams/dl-cross-language-research/scripts/generate_dl_seed_phase1.py
workstreams/dl-cross-language-research/.venv/bin/python \
  workstreams/dl-cross-language-research/scripts/run_dl_seed_phase1.py \
  --python workstreams/dl-cross-language-research/.venv/bin/python
workstreams/dl-cross-language-research/.venv/bin/python \
  workstreams/dl-cross-language-research/scripts/build_dl_uast_baseline.py \
  --binary runtime/uast-v0.2.18/uast4py-linux-amd64
```
