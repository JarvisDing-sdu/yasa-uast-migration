# Python UAST 迁移与构建问题总结

## 1. 项目目标

本次工作将 Python 的 UAST 生成方式从旧版外部 `uast4py` 二进制迁移到基于 Tree-sitter 的实现。

旧流程：

```text
Python 源码 → python-ast-builder.ts → 外部 uast4py → UAST JSON
```

新流程：

```text
Python 源码 → web-tree-sitter → tree-sitter-python.wasm → Python UAST
```

新的 Python parser 在 engine 内部直接运行，不再依赖 `uast4py`。

## 2. WASM 是什么

WASM 是 WebAssembly 的缩写，是一种可以被 JavaScript、Node.js 和浏览器执行的低层字节码格式。

在本项目中，Tree-sitter 的 Python 语法分析器被编译成：

```text
tree-sitter-python.wasm
```

`web-tree-sitter` 加载这个文件后，可以把 Python 源码解析成语法树，再由 Python parser 转换成项目使用的 UAST。

WASM 不是 UAST，也不是最终 AST。它主要提供语法分析能力；`parser.ts` 和 `visitor.ts` 负责把 Tree-sitter 的语法树转换成项目定义的 UAST 节点。

## 3. CST、AST 和 UAST 的关系

大致流程如下：

```text
源代码
  ↓
Tree-sitter CST/语法树
  ↓ Visitor 遍历和转换
语言 AST/UAST 节点
  ↓
YASA 分析器、规则和污点传播
```

Python 的 `parser.ts` 不只是加载语法树。它还负责节点映射、字段转换、位置信息、父子关系和 UAST 类型构造，因此可以认为它承担了从 Tree-sitter 语法树到项目 UAST 的转换工作。

PHP 的 parser 使用 `@ant-yasa/uast-parser-php`，转换逻辑主要封装在 PHP parser 包内部，所以 engine 中的 `php-ast-builder.ts` 看起来较短。

## 4. Python parser 与 PHP parser 的调用方式

原先两者的 import 方式不同：

```ts
// PHP
import * as TreeSitter from 'web-tree-sitter'

// Python
import { Parser as TreeParser, Language, type Node as SyntaxNode } from 'web-tree-sitter'
```

Python 已按 PHP 的方式统一为命名空间导入，并使用：

```ts
await TreeSitter.Parser.init()
TreeSitter.Language.load(...)
new TreeSitter.Parser()
```

这样可以统一初始化方式，也减少不同 parser 之间的调用差异。

## 5. 为什么迁移后速度可能快一倍

旧版 Python parser 每次解析通常需要：

1. 创建临时 Python 文件；
2. 启动外部 `uast4py` 进程；
3. 通过文件或进程输出读取 JSON；
4. 再把 JSON 转成 engine 内部对象。

新版 parser 在 Node.js 进程内加载一次 WASM grammar，之后直接解析内存中的源码。它减少了进程启动、临时文件、序列化和反序列化开销，因此在大量小文件场景下可能明显更快。

实际性能仍取决于文件数量、规则执行、worker 数量、缓存和机器环境，不能只根据单个样本断言固定提升一倍。

旧版依赖安装与 `uast4py` 问题

旧版 `YASA-Engine` 的 Python parser 依赖外部二进制：

```text
deps/uast4py/uast4py
```

`npm install` 不会安装它，因为它不是 npm 依赖。旧项目的 `install_deps.sh` 会根据平台下载：

```text
uast4go
uast4py
```

脚本没有执行权限时可以这样运行：

```bash
bash install_deps.sh
```

也可以补充执行权限：

```bash
chmod +x install_deps.sh
./install_deps.sh
```

在迁移后的 Python parser 中不需要再下载 `uast4py`。如果日志出现 `uast4go binary not found`，那是 Go parser 的旧外部依赖，与 Python UAST 无关。

## 8. `npm test-all` 执行哪些测试

`npm run test-all` 读取 `engine/package.json` 中的脚本，并按 `&&` 顺序执行：

```text
test-callargs
test-fastapi-backgroundtasks
test-match-field
test-entrypoint-deadline-budget
test-entrypoint-deadline-scheduler
test-clone-util
test-sink-util-new-expr
test-taint-output-strategy
test-go-dynamic-key-taint
test-js
test-java
test-sarif-codeflow-quality
test-go
test-python
test-callchain
test-php
```

其中任意一个测试失败，后面的测试不会继续执行。Java SARIF 测试需要先准备 benchmark：

```bash
npx tsx test/java/prepare-java-benchmark.ts
```

因此，`test-all` 失败不一定说明 Python parser 失败，也可能是 Go、Java、PHP 或测试资源问题。

## 9. 构建流程

迁移 engine 的构建流程大致为：

```text
安装依赖
  ↓
准备 native addon
  ↓
patch PHP WASM 资源
  ↓
TypeScript 类型检查
  ↓
运行全部测试
  ↓
tsc 编译到 dist
  ↓
pkg 打包
  ↓
清理 dist
```

`npx tsc --noEmit` 只做类型检查，不生成文件；`npx tsc` 才会把 TypeScript 编译到 `dist`。

如果构建在测试阶段失败，后面的编译和清理步骤不会执行。因此失败后可以手动删除：

```bash
rm -rf dist
```

## 10. pkg 打包问题

在 Apple Silicon 上打包多个目标时，项目配置通常包括：

```text
node18-macos-arm64
node18-macos-x64
node18-linux-x64
```

如果在 arm64 Mac 上出现：

```text
spawn Unknown system error -86
```

通常表示打包过程需要启动 x86_64 进程，但机器没有 Rosetta 2。可以安装：

```bash
softwareupdate --install-rosetta --agree-to-license
```

`pkg` 输出的 `prebuild-install` 和 `fs.R_OK deprecated` 多数是警告，不一定导致失败。

PHP WASM 如果直接使用裸的 `npx pkg .`，可能被 pkg 按文本处理，运行时出现：

```text
WebAssembly.instantiate(): unknown section code #0x3d
```

应使用项目的 `build.sh`，因为它会先执行 PHP WASM patch。

## 11. Python parser 初始化问题

Python parser 的解析接口是同步的，但 WASM 加载是异步的：

```ts
await PythonParser.ensureInitialized()
PythonParser.parseSingleFile(...)
```

如果只在 worker 中初始化，CLI 的 `--dumpAST` 或某些单文件路径仍可能报：

```text
Python parser not initialized. Call ensureInitialized() first.
```

最终采用的修复方式是在统一 parser 入口增加：

```ts
async function ensureInitialized(language?: string): Promise<void> {
  if (language === 'python') {
    const PythonParser = require('./python/python-ast-builder')
    await PythonParser.ensureInitialized()
  } else if (language === 'php') {
    const PhpParser = require('./php/php-ast-builder')
    await PhpParser.ensureInitialized()
  }
}
```

并在 `starter.ts` 确定语言后、进入 `dumpAST` 或 Analyzer 之前调用：

```ts
await Parser.ensureInitialized(Config.language)
```

这样覆盖普通分析、单文件分析和 `--dumpAST`。worker 内仍保留初始化逻辑，因为 worker 是独立 Node.js 进程。

## 12. 当前验证结果

Python 相关验证已经通过：

```text
npx tsc --noEmit       通过
npx tsc                通过
Python tree-sitter     通过
FastAPI Python 测试    通过
```

测试结果为：

```text
9 passing, 1 pending
```

重新构建后应使用新产物验证：

```bash
cd ~/Downloads/yasa-uast-migration/engine
./build.sh

./yasa-engine-macos-arm64 \
  /Users/infinite/Downloads/YASA-Engine/test/python/fastapi-backgroundtasks-cases/scanner_callback.py \
  --language python \
  --dumpAST
```
