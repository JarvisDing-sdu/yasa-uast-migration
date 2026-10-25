# 组件补丁

C 扩展的代码属于 `engine/` 和 `uast/` 两个子模块，对应独立仓库
`JarvisDing-sdu/yasa-engine` 和 `JarvisDing-sdu/yasa-uast`。本次开发会话没有这两个仓库的推送权限，所以把两个组件提交以 `git format-patch` 格式放在这里。它们已在 main（`6ce320b`）固定的子模块提交上验证过，可以直接应用。

| 目录 | 目标仓库 | 基线提交 | 内容 |
| --- | --- | --- | --- |
| `yasa-uast/` | `JarvisDing-sdu/yasa-uast` | `ebd02b8` | `parser-C/`、`.github/workflows/c-parser.yml` |
| `yasa-engine/` | `JarvisDing-sdu/yasa-engine` | `ed717ed` | CAnalyzer、C checker、规则、注册改动、`test/c` |

## 应用并更新子模块

```bash
# 1. 组件仓库：在一个新分支上应用补丁并推送
cd uast
git checkout -b c-extension ebd02b8
git am ../workstreams/yasa-c-extension/patches/yasa-uast/*.patch
git push -u origin c-extension

cd ../engine
git checkout -b c-extension ed717ed
git am ../workstreams/yasa-c-extension/patches/yasa-engine/*.patch
git push -u origin c-extension

# 2. 集成仓库：把子模块指针指向新提交
cd ..
git add uast engine
git commit -m "chore: point submodules to C extension commits"
```

先推送组件仓库，再更新子模块指针，否则别人检出时会找不到被指向的提交（与 README 中“两次提交”的规则一致）。
