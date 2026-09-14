# 深度学习跨语言 UAST 研究工作流

目标是利用 YASA UAST 提供的通用程序结构表示，构造并验证各语言深度学习框架程序的
功能/语义一致性，以发现框架实现或 API 映射中的异常差异。

```text
Python/PyTorch source
  → YASA UAST
  → DL Semantic Profile
  → Java/DJL、GoMLX、ONNX 等目标程序
  → 固定输入、权重、dtype、shape 下的差分执行
```

UAST 只表达通用语法结构；Tensor、算子、shape、dtype、device、训练/推理状态和权重
属于本工作流定义的 `DL Semantic Profile`，暂不修改 YASA 的通用 UAST specification。

目录说明：

- `docs/`：问题定义、DL 语义、训练/评测计划、PyTorch emitter 验证报告；
- `fixtures/`：可版本管理的 Phase 1 测试计划与样例元数据；
- `fixtures/generated/`：可再生的源码、UAST、运行 oracle 与 round-trip 产物，Git 忽略；
- `scripts/`：生成 PyTorch case、运行 oracle、生成旧 UAST 基线、验证 emitter；
- `benchmarks/pytorch-upstream/`：PyTorch 上游稀疏克隆，Git 忽略；
- `.venv/`：本地 PyTorch 运行环境，Git 忽略；
- `src/`：后续放 DL semantic extractor、目标框架生成器与 differential runner。

本工作流复用 `uast/emitter-Python/`，但不在其中加入 PyTorch 特定逻辑。
