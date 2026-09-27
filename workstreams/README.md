# 工作流目录

`engine/` 和 `uast/` 是 YASA 上游底座的 Git 子模块，必须保留在仓库根目录。
本目录只放围绕底座开展的工作材料：

- [yasa-python-migration](yasa-python-migration/README.md)：Python parser 从外部
  `uast4py` 迁移到 Node.js 进程内实现的验收、基线、回归与性能记录。

`dl-cross-language-research/` 是同一物理工作区中的私人研究目录，但不属于本公开
仓库；它由独立的私有 Git 仓库管理。

通用 Python UAST → Python 源码 emitter 位于 `uast/emitter-Python/`。它的实现与
通用 round-trip 验收归 Python parser 迁移工作流所有，属于企业交付范围。
