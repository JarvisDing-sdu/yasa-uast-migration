# uast4py tree-sitter 重构总结

## 1. 项目目标

本次工作将 YASA 的 Python UAST 生产解析链路从 Python `ast` + `uast4py`
二进制迁移到 `tree-sitter-python` WASM + TypeScript Visitor，使 Python 与 PHP
等语言采用一致的 npm Parser 生命周期：

```text
Python 源码
  -> tree-sitter-python WASM
  -> TypeScript Visitor
  -> YASA UAST
  -> YASA-Engine 统一 AST 后处理与安全分析
```

迁移以以下上游版本为基线：

- YASA-Engine：`249420d17656988138831956babebae456bfa6e1`
- YASA-UAST：`07e3823e56daaebe464626d7558e7fd2840674bf`（v0.2.18）
- 测试基准库：`alipay/ant-application-security-testing-benchmark`

## 2. 已完成工作

### 2.1 新增 Python npm Parser

在 `uast/parser-Python` 中新增 `@ant-yasa/uast-parser-python`：

- 使用 `web-tree-sitter@0.26.8` 加载 `tree-sitter-python@0.25.0` WASM。
- 提供 `await parser.init()` 和同步 `parser.parse()` 接口，与 PHP Parser 对齐。
- 初始化支持重复调用、并发调用和失败后重试。
- 每次解析完成后主动释放 tree-sitter 语法树。
- 返回共享 `@ant-yasa/uast-spec` 的 `CompileUnit`，保留旧协议字段和元数据。
- 支持构造时配置 `sourcefile`，也支持每次解析覆盖。
- 保留 UTF-8 字节列号、BOM 去除、旧版 `async`/`await` 标识符等兼容行为。

TypeScript Visitor 已覆盖分析所需的主要 Python 结构，包括：

- 变量、连续赋值、解构、类型注解及联合/泛型类型；
- 函数、参数类型、装饰器、类、构造器、dataclass；
- import、future import、相对导入和别名；
- if、for、while、try、with、异步语句；
- 调用、关键字参数、展开参数、属性、切片；
- list/dict/tuple、bytes、普通字符串及 f-string；
- yield、await、推导式、match 模式和 guard。

对多生成器推导式及 match guard 做了补全，避免旧 Visitor 丢失依赖关系。
调试 f-string（如 `f'{value=}'`）会保留标签文本、空白和表达式。

### 2.2 接入 YASA-Engine

Engine 的 Python 解析适配器已改为调用 npm Parser：

- 项目解析改走 Engine 的统一逐文件解析和 AST 后处理流程。
- worker 子进程会独立完成 WASM 初始化。
- 单文件分析支持直接使用内存源码缓存，不再要求磁盘临时文件。
- 删除生产链路对 uast4py 可执行文件、临时 JSON 文件及 Python 运行时的依赖。
- `install_deps.sh` 不再下载 uast4py，仅保留仍需的 Go Parser。
- pkg 资源配置加入 Python grammar 和 web-tree-sitter WASM。
- 增加实际等待 Engine 扫描完成的集成测试；旧异步测试显示 `0 passing`
  的问题不再影响本次回归结论。

Engine 当前通过 `file:../uast/parser-Python` 引用 Parser，适合本双仓库迁移工作区。
正式发布前应先发布 npm 包，再替换为正式版本号。

### 2.3 测试、CI 与发布准备

新增以下验证能力：

- Parser 单元测试和完整 `CompileUnit` 对照。
- 旧 Python Visitor 批量 oracle，仅在测试中使用。
- 任意 Python 项目的语法 corpus 测试和耗时/RSS 输出。
- 新旧 UAST 逐字段差分，包括 `loc` 和 `_meta`。
- Engine 新旧解析器独立进程扫描结果对比。
- Linux、macOS、Windows 的 Parser CI 配置。
- Python npm Parser 的 release job。

旧实现及旧二进制 release job 暂时保留，用于兼容尚未迁移的消费者和差分测试。

## 3. 本地验证结果

| 验证项 | 结果 |
| --- | --- |
| Python Parser TypeScript 构建 | 通过 |
| Parser 单测（启用旧实现 oracle） | 16/16 通过，无跳过 |
| 调试 f-string 专项对比 | 3 个样例语义一致；CPython 3.14 下位置也一致 |
| xAST `sast-python3` UAST 差分 | 800/800 完全一致，无位置差异 |
| Engine TypeScript `--noEmit` | 通过 |
| Engine tree-sitter 集成测试 | 4/4 通过 |
| Engine no-init-dispatch 回归 | 12 个文件、7 条检出；新旧完整链路一致 |
| npm `pack --dry-run` | 通过，9 个发布文件，约 14.9 kB |

xAST 对照版本为 `70e48aabac9b107c02bc46e97e7576fa81a0c4cf`。
800/800 表示原始 UAST 正文完全一致，不等同于已完成 800 文件的 Engine 全量规则检出对比。

使用本机 CPython 3.14.4 标准库及测试目录做额外语法覆盖：1850 个文件中
1822 个成功、28 个明确失败；初始化约 5.39 ms，读取加解析约 11.67 s，
进程 RSS 约 382 MiB。该目录包含故意无效的语法测试文件，这组数据用于发现
覆盖缺口，不作为新旧性能结论。

## 4. 已知边界

- 非 raw/bytes 的命名 Unicode 转义 `\N{...}` 尚未实现，当前明确抛错。
- Python 3.14 template string（`t'...'`）尚未映射，当前明确抛错。
- grammar 对部分 Python 3.14 泛型默认值、星号类型表达式及特殊跨行属性语法
  仍会报告语法错误。
- 相邻混合 f-string 的常量合并结构尚未全面与旧实现对齐。
- 多生成器推导式和 match guard 的增强映射还需要专项 Engine 规则回归。
- 尚未在远程 CI 执行三平台测试，也未完成 Engine pkg 独立可执行文件验证。
- 尚未执行完整 xAST 规则检出和严格的新旧性能/峰值内存对比。
- 尚未发布 npm 包或正式版本。

遇到尚未支持的结构时 Parser 会抛出错误，避免静默生成错误 UAST。

## 5. 复现命令

```bash
cd uast/parser-Python
npm ci --ignore-scripts
npm run build

python3 -m venv /tmp/yasa-python-oracle
/tmp/yasa-python-oracle/bin/pip install -r requirements.txt
PYTHON_UAST_ORACLE=/tmp/yasa-python-oracle/bin/python npm test
PYTHON_UAST_ORACLE=/tmp/yasa-python-oracle/bin/python \
  npm run test:compare -- /path/to/ant-application-security-testing-benchmark/sast-python3
npm pack --dry-run

cd ../../engine
npm ci --ignore-scripts
npx tsc --noEmit
PYTHON_UAST_ORACLE=/tmp/yasa-python-oracle/bin/python npm run test-python-tree-sitter
```

不设置 `PYTHON_UAST_ORACLE` 时，涉及旧实现的差分用例会明确跳过，不能视为
已完成兼容性对照。

## 6. 后续建议

1. 补齐命名 Unicode 转义及 template string 映射。
2. 对多生成器推导式、match guard 和混合 f-string 建立专项规则回归。
3. 在测试基准库上执行完整 Engine 新旧检出与性能对比。
4. 运行三平台 CI，并验证 pkg 打包后的 WASM 查找路径。
5. 发布 `@ant-yasa/uast-parser-python`，将 Engine 的本地依赖替换为正式版本。
6. 完成下游迁移后再移除旧 Python 实现和二进制发布流程。

## 7. 仓库分支布局

由于提交时没有独立的 YASA-UAST/YASA-Engine fork，本迁移仓库使用两个
可直接获取的快照分支承载子模块，避免根仓库引用无法从远端下载的本地提交：

- `submodule/uast-python-tree-sitter`：包含本次 Parser 实现的完整 UAST 快照。
- `submodule/engine-python-tree-sitter`：包含本次 Engine 接入的完整快照。
- `main`：迁移说明、总结文档和上述两个子模块的精确提交引用。

两个快照都是无父提交，以避免把上游仓库的完整历史重复推入迁移仓库。
本地仍保留基于上游固定提交的正常开发分支，可用于后续生成上游补丁或 PR。
