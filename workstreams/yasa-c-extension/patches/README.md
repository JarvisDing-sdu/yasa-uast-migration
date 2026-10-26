# 组件补丁

C 扩展的代码属于 `engine/` 和 `uast/` 两个子模块，对应独立仓库
`JarvisDing-sdu/yasa-engine` 和 `JarvisDing-sdu/yasa-uast`。这里以 `git format-patch` 格式保存最近一轮（语义修复，见 `docs/C扩展-语义修复报告.md`）的组件提交，便于审阅和在没有推送权限时应用。集成仓库的子模块指针已指向这两个提交；若组件仓库中还没有这两个提交，先按下面的步骤推送，再更新集成仓库，避免子模块指针指向取不到的提交。

| 目录 | 目标仓库 | 基线提交（main） | 内容 |
| --- | --- | --- | --- |
| `yasa-uast/` | `JarvisDing-sdu/yasa-uast` | `be5277a` | parser-C 按编译配置预处理（`src/macros.ts`、`src/parser.ts`、单测） |
| `yasa-engine/` | `JarvisDing-sdu/yasa-engine` | `3fc472c` | CAnalyzer 语义修复、`c-types.ts`、`c-const-eval.ts`、libc 模型、checker、`--c*` 选项、`test/c` 语义回归 |

## 应用

```bash
cd uast
git checkout -b c-semantics be5277a
git am ../workstreams/yasa-c-extension/patches/yasa-uast/*.patch
git push -u origin c-semantics

cd ../engine
git checkout -b c-semantics 3fc472c
git am ../workstreams/yasa-c-extension/patches/yasa-engine/*.patch
git push -u origin c-semantics
```
