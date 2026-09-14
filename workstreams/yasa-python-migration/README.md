# YASA Python parser 迁移工作流

目标是将 Python 的生产解析链路从外部 `uast4py` binary 迁移到 Node.js 进程内的
Tree-sitter parser，同时保持 UAST 协议、YASA finding、污点 trace 和性能验收可比较。

```text
Python source → parser-Python → UAST → Engine → YASA finding
```

目录说明：

- `docs/`：旧 parser 基线、Tree-sitter 重构说明、xAST/OWASP 回归和性能记录；
- `scripts/`：旧 source parser 与 binary 的 UAST 对比、OWASP 文件级评分；
- `reports/`：本机生成的可再生报告（通常不提交）。

核心代码仍在上游子模块中：

- `uast/parser-Python/`：新的 Tree-sitter/WASM TypeScript parser；
- `engine/src/engine/parser/python/`：Engine 接入层；
- `uast/emitter-Python/`：通用 Python UAST → Python 源码 emitter。

emitter 的作用是检查 UAST round-trip 及信息损失，不读取 PyTorch 输出，也不承担跨语言
深度学习语义翻译。其说明见 [Python UAST 双侧还原：小样例](docs/Python-UAST双侧还原-小样例.md)。

常用验收文档：

- [最新进展与验收状态](docs/Python解析器迁移-最新进展与验收状态.md)
- [Python UAST 语义单测](docs/Python-UAST语义单测.md)
- [旧新 UAST 双侧还原：小样例](docs/Python-UAST双侧还原-小样例.md)
- [PyTorch 真实源码解析与还原](docs/PyTorch真实源码-解析与还原.md)
- [OWASP Python 旧新回归](docs/OWASP-Python-旧新回归.md)
- [xAST 检出与性能对比](docs/xAST-检出与性能对比.md)
