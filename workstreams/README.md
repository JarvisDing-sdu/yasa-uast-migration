# 工作流目录

`engine/` 和 `uast/` 是 YASA 上游底座的 Git 子模块，必须保留在仓库根目录。
本目录只放围绕底座开展的工作材料：

- [yasa-python-migration](yasa-python-migration/README.md)：Python parser 从外部
  `uast4py` 迁移到 Node.js 进程内实现的验收、基线、回归与性能记录。
- [dl-cross-language-research](dl-cross-language-research/README.md)：以 UAST 为
  通用语法表示、面向深度学习框架跨语言语义一致性测试的研究工作。

通用 Python UAST → Python 源码 emitter 位于 `uast/emitter-Python/`。它的实现与
通用 round-trip 验收归前一条工作流所有；后一条工作流可以调用它来验证 PyTorch 样例，
但不应向 emitter 注入 Tensor 或框架特定语义。
