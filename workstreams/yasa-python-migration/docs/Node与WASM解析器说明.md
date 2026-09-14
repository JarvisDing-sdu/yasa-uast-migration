# 新 Python parser 里的 npm、WASM 与 Engine 调用关系

本文解释新 Python parser 为什么出现在 Node.js/npm 体系中，以及它与 PHP parser、
Engine 的关系。

## 1. 一句话结论

新 Python parser 的结构是：

```text
Python 源码
  → tree-sitter-python.wasm：识别 Python 语法
  → TypeScript Visitor：翻译成 YASA UAST
  → Engine：做调用图、污点分析和 SARIF 报告
```

WASM 负责“看懂 Python 语法”；TypeScript 代码负责“转成 YASA UAST”。

## 2. npm 是什么

npm 是 Node.js 的包管理工具。它类似 Python 的 `pip`，但还会定义测试、构建和打包命令。

| Python | Node.js |
| --- | --- |
| `requirements.txt` / `pyproject.toml` | `package.json` |
| `pip install` | `npm install` / `npm ci` |
| `.venv/lib/...` | `node_modules/...` |
| `pytest` | `npm test` |

执行：

```bash
cd uast/parser-Python
npm ci
```

npm 会根据 `package-lock.json` 下载锁定版本的依赖，放在 `node_modules/`。`node_modules`
不是 Git 源码的一部分，clone 后通常不存在；安装依赖后才出现。

新 Python parser 的 [package.json](../../../uast/parser-Python/package.json) 声明：

```json
{
  "name": "@ant-yasa/uast-parser-python",
  "dependencies": {
    "@ant-yasa/uast-spec": "^0.2.18",
    "tree-sitter-python": "0.25.0",
    "web-tree-sitter": "0.26.8"
  },
  "scripts": {
    "build": "tsc",
    "test": "node --import tsx --test tests/*.test.ts"
  }
}
```

含义是：这个目录本身被定义为一个可被 Node.js 引用的包；它需要 UAST 定义、
Tree-sitter 运行库和 Python grammar。

## 3. WASM 文件是什么

WASM（WebAssembly）是一种可由 Node.js 或浏览器加载执行的二进制格式。这里的：

```text
uast/parser-Python/node_modules/tree-sitter-python/tree-sitter-python.wasm
```

不是整个 Python 解释器，而是 Tree-sitter 的 Python 语言 grammar。它知道：

```python
def f(x):
    return x + 1
```

分别是函数、参数、返回语句、二元表达式和标识符，但不知道 YASA UAST、污点或漏洞。

新 parser 的 [src/parser.ts](../../../uast/parser-Python/src/parser.ts) 在初始化时：

```ts
const grammarRoot = dirname(require.resolve('tree-sitter-python/package.json'));
const language = await Language.load(
  join(grammarRoot, 'tree-sitter-python.wasm')
);
const instance = new TreeParser();
instance.setLanguage(language);
```

它先从 `node_modules` 找到 `tree-sitter-python` 包，再加载其中的 `.wasm` grammar，
并把 grammar 设置给 Tree-sitter parser。之后每次执行 `parser.parse(content)` 都会使用
已经加载到内存中的 grammar；不会每个文件重新下载。

每个 Engine worker 是独立 Node.js 进程，因此每个 worker 会各自初始化一份 WASM。

## 4. 为什么还有 Visitor

Tree-sitter 给出的结果是“Python 语法树”，不是 YASA UAST。

```text
tree-sitter-python.wasm
  → function_definition / return_statement / identifier 等语法节点
  → src/visitor.ts
  → FunctionDefinition / ReturnStatement / Identifier 等 YASA UAST 节点
```

真正把 Tree-sitter 语法树转换成 YASA UAST 的代码是：

[src/visitor.ts](../../../uast/parser-Python/src/visitor.ts)。

## 5. Engine 如何调用新 parser

Engine 的 [package.json](../../../engine/package.json) 写着：

```json
"@ant-yasa/uast-parser-python": "file:../uast/parser-Python"
```

这表示当前不是从 npm 公共仓库下载 Python parser，而是把相邻目录
`uast/parser-Python` 当作一个本地 npm 包使用。

Engine 的 Python 适配层：

[engine/src/engine/parser/python/python-ast-builder.ts](../../../engine/src/engine/parser/python/python-ast-builder.ts)

核心代码是：

```ts
const { Parser: PythonUastParser } = require('@ant-yasa/uast-parser-python');

await pythonParser.init();
return pythonParser.parse(code, options);
```

因此生产路径为：

```text
Engine CLI
  → Engine Python adapter
  → @ant-yasa/uast-parser-python
  → tree-sitter-python.wasm + TypeScript Visitor
  → UAST
  → Engine 污点分析
```

`engine/src/engine/parser/python/` 是适配器目录，不是完整 Python 语法 parser 的实现位置。
真正 parser 在 `uast/parser-Python/src/`。

## 6. PHP 为什么看起来更简洁

PHP parser 实际上也是同一架构。它的 [package.json](../../../uast/parser-PHP/package.json)
同样依赖：

```json
"tree-sitter-php": "^0.24.2",
"web-tree-sitter": "^0.26.8"
```

PHP 的 [src/parser.ts](../../../uast/parser-PHP/src/parser.ts) 也会加载：

```ts
require.resolve('tree-sitter-php/tree-sitter-php.wasm')
```

差别主要是安装位置：

```text
PHP：Engine 依赖的是已发布的 npm 包；其依赖通常在 engine/node_modules/
Python：当前 Engine 依赖的是本地 file:../uast/parser-Python；
        我们为构建和测试在该目录执行过 npm ci，依赖在其 node_modules/
```

所以 PHP 目录里没有单独 `node_modules`，不代表 PHP 不使用 npm；它是作为 Engine 的
间接依赖安装的。注意 PHP parser 当前没有 `package-lock.json`，若要在该目录独立安装，
应执行 `npm install`；`npm ci` 必须有 lock 文件才可执行。两者都采用
“npm + Tree-sitter WASM + Visitor → UAST”的模式。

## 7. 新旧 Python parser 同时存在的原因

`uast/parser-Python/` 中有两套实现：

```text
src/             新：TypeScript + Node.js + Tree-sitter WASM，生产使用
uast/visitor.py  旧：Python ast Visitor，仅用于新旧差分 oracle
```

旧实现暂时保留，是为了比较新 parser 是否改变 UAST 或 YASA finding；确认迁移验收完成前
不能删除。
