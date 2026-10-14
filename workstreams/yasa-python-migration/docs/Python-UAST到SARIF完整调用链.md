# Python UAST 到 SARIF 的完整调用链

本文说明 YASA Engine 扫描 Python 项目时，从命令行启动、Python 源码解析、UAST 构造、静态分析、Checker 检测，到最终生成 SARIF 报告的完整流程，并明确各层之间的职责边界。

## 1. 总体调用链

需要特别注意：`tree-sitter-python.wasm` 不会直接生成 UAST。它生成的是 Tree-sitter CST，真正将 CST 转换成 YASA UAST 的是 `uast/parser-Python/src/visitor.ts`。

```text
命令行
  ↓
engine/src/main.ts
  ↓
engine/src/interface/starter.ts
  ├─ 解析参数、选择语言和 Analyzer
  ├─ 初始化 Python WASM parser
  └─ 驱动分析、输出结果
  ↓
engine/src/engine/parser/parser.ts
  ├─ 查找 Python 文件
  ├─ 读取源码、缓存源码
  ├─ 调用 Python parser
  └─ UAST 通用后处理
  ↓
engine/src/engine/parser/python/python-ast-builder.ts
  └─ Engine 与 Python UAST 包之间的适配层
  ↓
@ant-yasa/uast-parser-python
  ↓
uast/parser-Python/src/index.ts
  ↓
uast/parser-Python/src/parser.ts
  ├─ 加载 web-tree-sitter
  ├─ 加载 tree-sitter-python.wasm
  └─ Python 源码 → Tree-sitter CST
  ↓
uast/parser-Python/src/visitor.ts
  └─ Tree-sitter CST → YASA UAST
  ↓
Engine Parser 通用后处理
  ├─ sourcefile
  ├─ parent
  ├─ nodehash
  └─ 缓存
  ↓
PythonAnalyzer
  ├─ 建立模块、作用域和符号表
  ├─ 发现 entrypoint
  ├─ 模拟执行 UAST
  └─ 传播 Value 和 taint
  ↓
CheckerManager
  ↓
taint_flow_test / Python Checker / 其他 Checker
  ├─ 标记 source
  ├─ 识别 sink
  ├─ 处理 sanitizer
  └─ 产生 finding
  ↓
ResultManager
  ↓
TaintOutputStrategy
  ↓
report.sarif
```

## 2. `engine/src/main.ts`：进程入口

`main.ts` 是 YASA Engine 的最外层程序入口，但它本身基本不包含分析业务。

核心逻辑相当于：

```ts
const args = process.argv.slice(2)
await execute(null, args)
```

它的职责是：

1. 从 `process.argv` 读取命令行参数；
2. 调用 `starter.ts` 导出的 `execute()`；
3. 捕获没有被下层处理的异常；
4. 设置进程退出码。

例如执行：

```bash
./yasa-engine project/ \
  --language python \
  --checkerIds taint_flow_test \
  --reportDir output
```

`main.ts` 得到的参数大致是：

```ts
[
  'project/',
  '--language',
  'python',
  '--checkerIds',
  'taint_flow_test',
  '--reportDir',
  'output',
]
```

`main.ts` 不负责解析 Python、构造 UAST、传播污点或生成 SARIF。它只是启动整个流程。

## 3. `engine/src/interface/starter.ts`：扫描流程编排层

`starter.ts` 是 CLI 与 Engine 核心之间的编排层，可以理解为整个扫描过程的“总导演”。

### 3.1 `execute()` 控制完整生命周期

`main.ts` 调用：

```ts
execute(null, args)
```

`execute()` 的主要流程是：

```text
解析配置
→ 创建 Analyzer
→ 执行 Analyzer
→ 获取 findings
→ 调用输出策略
→ 生成报告
```

对应的关键调用是：

```ts
const analyzer = await initAnalyzer(dir, args, printf)
const exitCode = await executeAnalyzer(analyzer, processingDir)
result = await outputAnalyzerResult(analyzer, printf)
```

三个阶段分别是：

| 阶段 | 方法 | 作用 |
| --- | --- | --- |
| 初始化 | `initAnalyzer()` | 解析参数、选择语言、加载 Checker、创建 Analyzer |
| 分析 | `executeAnalyzer()` | 调用 `analyzeSingleFile()` 或 `analyzeProject()` |
| 输出 | `outputAnalyzerResult()` | 把 findings 转换为 SARIF 等报告 |

### 3.2 解析命令行配置

`starter.ts` 将命令行选项写入全局 `Config`，常见字段包括：

```text
Config.maindir
Config.language
Config.analyzer
Config.checkerIds
Config.checkerPackIds
Config.reportDir
Config.dumpAST
Config.single
```

例如：

```bash
--language python --checkerIds taint_flow_test
```

会得到类似配置：

```ts
Config.language = 'python'
Config.checkerIds = ['taint_flow_test']
```

这些配置随后会传给 Parser、PythonAnalyzer、CheckerManager 和报告输出策略。

### 3.3 选择 Analyzer

当语言是 Python，且用户没有显式指定 Analyzer 时，`starter.ts` 会选择：

```text
PythonAnalyzer
```

然后创建：

```ts
new PythonAnalyzer(Config)
```

构造 `PythonAnalyzer` 时，还会根据 `Config.checkerIds` 和 `Config.checkerPackIds` 创建 `CheckerManager` 并加载 Checker。

### 3.4 初始化 WASM Parser

Python 和 PHP 的 Parser 使用 WASM。WASM 加载是异步操作，因此进入同步解析接口前必须执行：

```ts
await Parser.ensureInitialized(Config.language)
```

Python 初始化最终会加载：

```text
web-tree-sitter.wasm
tree-sitter-python.wasm
```

之所以需要提前初始化，是因为后续 Engine 使用的是同步接口：

```ts
Parser.parseSingleFile(...)
```

而初始化是异步的：

```ts
await pythonParser.init()
```

因此必须先完成异步初始化，再进入同步解析阶段。

### 3.5 执行 Analyzer

单文件扫描调用：

```ts
await analyzer.analyzeSingleFile(source, processingDir)
```

项目扫描调用：

```ts
await analyzer.analyzeProject(processingDir)
```

### 3.6 输出 Analyzer 结果

分析完成后，`starter.ts` 调用：

```ts
outputAnalyzerResult(analyzer, printf)
```

它从 Analyzer 中取得 `ResultManager`，再根据 finding 所属的输出策略调用：

```ts
strategy.outputFindings(...)
```

污点结果使用的策略 ID 是 `taintflow`，最终由 `TaintOutputStrategy` 写入 `report.sarif`。

## 4. `engine/src/engine/parser/parser.ts`：统一多语言解析层

`parser.ts` 是 Engine 的统一多语言解析入口。它让 Analyzer 不必关心 Java、Python、JavaScript、PHP 和 Go 分别使用什么解析器。

### 4.1 注册 Python Parser

Python 的注册配置大致为：

```ts
this.registry.register({
  language: 'python',
  unit: 'file',
  supportsIncremental: false,
  parseAsFiles: true,
  filePatterns: ['**/*.(py)', ...],
  parseSingleFile(code, options) {
    return PythonParser.parseSingleFile(code, options)
  },
  parseProject: async (rootDir, options) => {
    return PythonParser.parseProject(rootDir, options)
  },
  needsSourcefile: true,
})
```

这份配置说明：

- Python 的分析单元是文件；
- Python 项目按文件解析；
- 使用 `.py` 文件匹配规则；
- 实际语言适配器是 `python-ast-builder.ts`；
- 需要为节点设置 `sourcefile`。

### 4.2 单文件解析

Analyzer 调用：

```ts
Parser.parseSingleFile(filepath, options, sourceCodeCache)
```

这里第一个参数是文件路径，而不是源码。统一 Parser 会：

1. 从 `sourceCodeCache` 或磁盘读取源码；
2. 根据 `options.language` 找到 Python Parser；
3. 调用 `python-ast-builder.ts`；
4. 得到语言 Parser 返回的 UAST；
5. 执行 Engine 通用后处理；
6. 将结果返回 Analyzer。

### 4.3 项目解析

PythonAnalyzer 会调用：

```ts
Parser.parseProject(dir, options, sourceCodeCache)
```

当前 `python-ast-builder.parseProject()` 返回 `null`，表示语言适配器本身不执行项目批量解析。PythonAnalyzer 随后对未被解析的文件逐个调用：

```ts
Parser.parseSingleFile(...)
```

所以当前 Python 项目解析的实际过程是：

```text
查找所有 .py 文件
→ 逐文件 parseSingleFile
→ 汇总成“文件路径 → UAST”的映射
```

### 4.4 UAST 通用后处理

语言 Parser 返回 UAST 后，Engine 还会补充静态分析运行期所需的信息，例如：

- 设置 `loc.sourcefile`；
- 建立 `parent` 指针；
- 生成节点 hash；
- 注册到 AST Manager；
- 处理解析缓存；
- 维护源代码行缓存。

因此存在两个不同阶段：

```text
visitor.ts
→ 生成符合 UAST 数据模型的节点

Engine parser.ts
→ 给 UAST 补充静态分析运行期信息
```

## 5. `python-ast-builder.ts`：Engine 与 UAST 包的适配器

文件位置：

```text
engine/src/engine/parser/python/python-ast-builder.ts
```

这个名字是历史遗留。迁移后的文件不再真正构造每个 UAST 节点，它当前更接近：

```text
python-parser-adapter.ts
```

### 5.1 创建 UAST Parser 实例

```ts
const { Parser: PythonUastParser } =
  require('@ant-yasa/uast-parser-python')

const pythonParser = new PythonUastParser()
```

Engine 的 `package.json` 使用本地依赖：

```json
"@ant-yasa/uast-parser-python": "file:../uast/parser-Python"
```

所以这个 npm 包实际对应仓库中的：

```text
uast/parser-Python
```

### 5.2 保证只初始化一次

适配器使用：

```ts
let initialized = false
let initialization: Promise<void> | null = null
```

`ensureInitialized()` 保证：

- 同一个 Engine 进程只初始化一次；
- 并发初始化调用共享同一个 Promise；
- 初始化失败后允许重试；
- 初始化成功后的调用直接返回。

最终执行：

```ts
await pythonParser.init()
```

### 5.3 转交源码进行解析

```ts
function parseSingleFile(code, options) {
  if (!initialized) {
    throw new Error(...)
  }
  return pythonParser.parse(code, options)
}
```

它不会遍历 Python 语法，也不会亲自创建 `CallExpression`、`Identifier` 等节点，只负责把 Engine 传来的源码交给 UAST 包。

### 5.4 为什么保留这一层

这一层隔离了两个工程边界：

```text
YASA Engine
↕
Python UAST npm 包
```

如果以后 Python UAST 包修改初始化方式、解析参数、错误处理或发布方式，主要只需要修改这个适配器，而不需要改动整个 Analyzer。

## 6. `@ant-yasa/uast-parser-python`：包级 API

`@ant-yasa/uast-parser-python` 是 npm 包名，当前映射到：

```text
uast/parser-Python
```

包入口是：

```text
uast/parser-Python/src/index.ts
```

它导出统一的 Parser 类：

```ts
export class Parser {
  async init() {
    await pythonParser.init()
  }

  parse(content, opts) {
    return pythonParser.parse(content, opts)
  }
}
```

这个入口提供稳定的包级 API：

```ts
const parser = new Parser()
await parser.init()
const uast = parser.parse(code)
```

它使 Python Parser 和 PHP Parser 使用相近的生命周期：

```text
异步 init()
同步 parse()
```

## 7. `uast/parser-Python/src/parser.ts`：源码到 CST

这一层负责：

```text
Python 源码文本
→ Tree-sitter CST
→ 调用 Visitor
```

### 7.1 初始化 Tree-sitter Runtime

```ts
await TreeSitter.Parser.init()
```

这一步初始化 `web-tree-sitter` 的 WASM runtime，相当于加载 Tree-sitter 的运行引擎。

### 7.2 加载 Python Grammar

Parser 定位 `tree-sitter-python.wasm`，然后执行：

```ts
const language = await TreeSitter.Language.load(wasmPath)
const instance = new TreeSitter.Parser()
instance.setLanguage(language)
```

`tree-sitter-python.wasm` 描述 Python 的语法规则，例如：

- 函数和类定义；
- 调用表达式；
- 参数列表；
- `if`、`for`、`while`、`match`；
- 运算符和优先级；
- 字符串、数字和注释。

### 7.3 解析源码

```ts
tree = parser.parse(content)
```

输出的是 Tree-sitter CST，而不是 UAST。

例如：

```python
result = source()
```

对应的 CST 大致是：

```text
module
└── expression_statement
    └── assignment
        ├── left: identifier "result"
        └── right: call
            └── function: identifier "source"
```

这些名称属于 Tree-sitter Python grammar，不属于 YASA UAST。

### 7.4 兼容与错误处理

这一层还负责：

- 去除 UTF-8 BOM；
- 兼容旧代码中作为普通标识符使用的 `async` / `await`；
- 检查 Tree-sitter 语法错误；
- 在异常中携带文件名、行号和列号；
- 解析完成后释放 Tree-sitter tree。

### 7.5 调用 Visitor

语法解析成功后执行：

```ts
return new Visitor(content, opts.sourcefile)
  .compile(tree.rootNode)
```

从这一句开始进入 CST 到 UAST 的转换阶段。

## 8. `tree-sitter-python.wasm`：Python 语法识别器

`tree-sitter-python.wasm` 是编译后的 Python grammar。它不是 Python 编译器，也不是 UAST Builder。

它的输入是：

```text
Python 源代码字符
```

输出是：

```text
Tree-sitter Concrete Syntax Tree
```

它认识：

```text
function_definition
assignment
call
attribute
if_statement
for_statement
```

但不认识 YASA 的：

```text
CompileUnit
FunctionDefinition
VariableDeclaration
CallExpression
MemberAccess
RangeStatement
```

这两套节点之间的转换由 `visitor.ts` 完成。

## 9. `uast/parser-Python/src/visitor.ts`：CST 到 UAST

这是 Python UAST 迁移中最核心的实现文件，负责：

```text
Tree-sitter CST
→ YASA UAST
```

### 9.1 创建统一节点

`make()` 统一创建 UAST 节点：

```ts
{
  type,
  loc,
  _meta,
  ...默认字段,
  ...具体字段,
}
```

每个节点通常包含：

- `type`：UAST 节点类型；
- `loc`：源代码位置；
- `_meta`：静态分析辅助信息；
- 当前节点类型特有的字段。

### 9.2 根节点

整个 Python 文件会转换为：

```ts
{
  type: 'CompileUnit',
  language: 'python',
  body: [...],
  uri: null,
  version: null,
  languageVersion: '3.13',
}
```

### 9.3 常见节点映射

| Python CST | YASA UAST |
| --- | --- |
| `function_definition` | `FunctionDefinition` |
| `class_definition` | 类相关的对象结构 |
| `assignment` | `VariableDeclaration` 或 `AssignmentExpression` |
| `call` | `CallExpression` |
| `attribute` | `MemberAccess` |
| `if_statement` | `IfStatement` |
| `for_statement` | `RangeStatement` |
| `return_statement` | `ReturnStatement` |
| `binary_operator` | `BinaryExpression` |
| `identifier` | `Identifier` |
| 数字、字符串、布尔值 | `Literal` |
| `import_statement` | `ImportExpression` |
| Python 类型注解 | `PrimitiveType`、`ArrayType`、`MapType` 等 |

### 9.4 统一不同语言表达

例如 Python：

```python
obj.name
```

会转换成类似：

```ts
{
  type: 'MemberAccess',
  object: ...,
  property: ...,
  computed: false,
}
```

JavaScript 中的 `obj.name` 也会转换为相似结构。这就是 UAST 的意义：后续 Analyzer 可以面向统一节点工作，而不必直接理解每种语言的原始语法树。

### 9.5 源码位置

Visitor 同时计算：

```ts
loc: {
  start: { line, column },
  end: { line, column },
  sourcefile,
}
```

这些位置后续用于：

- 问题定位；
- 污点传播轨迹；
- SARIF location；
- 源码 snippet；
- IDE 或平台展示。

## 10. `PythonAnalyzer`：程序语义和抽象执行

文件位置：

```text
engine/src/engine/analyzer/python/common/python-analyzer.ts
```

Parser 解决的是“代码在语法上长什么样”，PythonAnalyzer 解决的是：

> 这些代码执行时，变量、函数、调用、对象和污点可能怎样流动？

### 10.1 创建 CheckerManager

构造 PythonAnalyzer 时会创建：

```ts
const checkerManager = new CheckerManager(
  options,
  options.checkerIds,
  options.checkerPackIds,
  options.printers,
  BasicRuleHandler,
)
```

然后传给 Analyzer 基类：

```ts
super(checkerManager, options)
```

所以 Checker 从 Analyzer 创建时就已经接入分析流程。

### 10.2 预处理项目

项目分析调用：

```ts
PythonAnalyzer.preProcess(dir)
```

内部进入：

```ts
scanModules(dir)
```

该阶段会：

1. 查找所有 `.py` 文件；
2. 读取源代码；
3. 填充 `sourceCodeCache`；
4. 调用 Parser 生成每个文件的 UAST；
5. 给 UAST 增加分析信息；
6. 逐个处理模块。

### 10.3 `addASTInfo()`

这一阶段补充 Analyzer 运行所需的信息，例如：

- 节点与源码之间的关系；
- parent 关系；
- node hash；
- AST Manager 注册；
- pretty print；
- SourceLine 信息。

这些信息之后会进入 finding 和 SARIF。

### 10.4 `processModule()`

`processModule()` 遍历每个 `CompileUnit`，建立：

- 模块模型；
- 全局作用域；
- 函数符号；
- 类和对象；
- import 关系；
- 变量声明；
- 函数闭包；
- entrypoint 候选。

它把树状语法结构转换成可以进行静态执行的程序模型。

### 10.5 `symbolInterpret()`

这是静态分析的主要执行阶段。Analyzer 对发现的 entrypoint 逐个进行抽象执行，包括：

- 执行赋值；
- 解析标识符；
- 模拟函数调用；
- 传播参数；
- 处理返回值；
- 处理成员访问；
- 处理条件和循环；
- 跨函数传播 Value；
- 跨调用传播 taint。

Analyzer 不会真正运行 Python 程序，而是用内部抽象 `Value` 模拟程序状态。

例如：

```python
data = request.args['name']
os.system(data)
```

可能被抽象为：

```text
request.args['name']
→ Value(tainted)
→ 赋值给 data
→ data 作为参数传给 os.system
→ sink 命中
```

## 11. `CheckerManager`：Analyzer 与规则之间的事件总线

文件位置：

```text
engine/src/engine/analyzer/common/checker-manager.ts
```

### 11.1 加载 Checker

Checker 配置来自：

```text
engine/resource/checker/checker-config.json
```

例如：

```json
{
  "checkerId": "taint_flow_test",
  "checkerPath": "checker/taint/test-taint-checker.ts"
}
```

CheckerManager 根据 `checkerIds` 和 `checkerPackIds` 找到对应文件并注册 Checker。

### 11.2 注册分析检查点

Checker 一般不自己从头遍历整棵 UAST。PythonAnalyzer 在分析过程中触发检查点，例如：

```text
checkAtStartOfAnalyze
checkAtCompileUnit
checkAtVariableDeclaration
checkAtAssignment
checkAtIdentifier
checkAtMemberAccess
checkAtFuncCallSyntax
checkAtFunctionCallBefore
checkAtFunctionCallAfter
checkAtEndOfNode
checkAtEndOfAnalyze
```

基本职责关系是：

```text
PythonAnalyzer：理解并模拟程序
Checker：在关键时机检查安全规则
```

例如 Analyzer 分析函数调用前后，会分别触发：

```ts
checkerManager.checkAtFunctionCallBefore(...)
checkerManager.checkAtFunctionCallAfter(...)
```

Checker 可以在这些检查点：

- 判断调用是不是 source；
- 判断调用是不是 sink；
- 判断是否命中 sanitizer；
- 给返回值增加 taint；
- 读取参数携带的 taint；
- 创建安全问题 finding。

## 12. `taint_flow_test` 与其他 Checker

`taint_flow_test` 对应：

```text
engine/src/checker/taint/test-taint-checker.ts
```

它是回归测试使用的 Checker，主要验证：

- source 是否正确产生污点；
- taint 是否经过变量和函数传播；
- sink 是否被正确发现；
- trace 是否完整；
- SARIF 是否包含预期结果。

生产环境中的 Python Checker 包括：

- `python-default-taint-checker.ts`；
- `python-taint-checker.ts`；
- `django-taint-checker.ts`；
- `tornado-taint-checker.ts`；
- `httpserver-taint-checker.ts`；
- `script-taint-checker.ts`。

它们共享的分析模型是：

```text
Source
→ Taint propagation
→ Sanitizer
→ Sink
→ Finding
```

### 12.1 Source

Source 表示外部不可信数据，例如：

```python
request.args.get('name')
input()
```

Checker 会给对应的抽象 Value 添加 taint tag。

### 12.2 Taint propagation

Analyzer 负责在以下操作中传播 taint：

- 变量赋值；
- 函数参数；
- 函数返回值；
- 对象字段；
- 容器元素；
- 成员调用；
- 表达式计算；
- 跨函数调用。

### 12.3 Sanitizer

如果数据经过清洗函数，Checker 可以记录 sanitizer 信息，或移除、限制对应类别的 taint。

### 12.4 Sink

Sink 是危险操作，例如：

```python
os.system(...)
subprocess.call(...)
cursor.execute(...)
eval(...)
```

当 sink 参数带有匹配的 taint 时，Checker 创建 finding。

## 13. `ResultManager`：收集 Finding

文件位置：

```text
engine/src/engine/analyzer/common/result-manager.ts
```

Checker 发现问题后不会直接写 SARIF，而是先创建 finding。Finding 通常包含：

- 漏洞描述；
- 严重等级；
- 源文件；
- sink 节点；
- entrypoint；
- 污点 trace；
- callstack；
- sinkInfo；
- sanitizer 信息。

然后调用类似：

```ts
resultManager.newFinding(finding, 'taintflow')
```

ResultManager 按输出策略分类保存：

```ts
findings = {
  taintflow: [...],
  callgraph: [...],
  callchain: [...],
}
```

这一设计将“发现安全问题”和“选择输出格式”分离，Checker 不需要了解 SARIF JSON 的具体结构。

## 14. 从 Finding 到 SARIF

污点输出策略位于：

```text
engine/src/checker/common/output/taint-output-strategy.ts
```

它对应：

```ts
outputStrategyId = 'taintflow'
outputFilePath = 'report.sarif'
```

### 14.1 获取污点 Findings

```ts
const allFindings = resultManager.getFindings()
const taintFindings = allFindings['taintflow']
```

### 14.2 去重和聚合

输出前会对 finding 去重，例如保留相同 source/sink 中更合适或更短的 trace。

后续还会将同一个 sink、同一个 entrypoint 的多条路径聚合为一个 SARIF result 中的多个 `codeFlows`。

### 14.3 构造污点路径

Finding 中的 trace 会转换为 SARIF：

```text
codeFlows
└── threadFlows
    └── locations
        ├── Step 0: source
        ├── Step 1: 赋值
        ├── Step 2: 参数传递
        └── Step 3: sink
```

每个 location 包含类似：

```json
{
  "physicalLocation": {
    "artifactLocation": {
      "uri": "example.py"
    },
    "region": {
      "startLine": 10,
      "startColumn": 5,
      "endLine": 10,
      "endColumn": 20,
      "snippet": {
        "text": "os.system(data)"
      }
    }
  }
}
```

这里使用的源码位置最初由 `visitor.ts` 生成，之后经过 Engine 后处理和 FindingUtil 转换为 SARIF 坐标。

### 14.4 构造 SARIF Result

每个漏洞最终得到类似结构：

```json
{
  "message": {
    "text": "Untrusted data reaches command execution"
  },
  "level": "error",
  "rank": 8,
  "entrypoint": {},
  "sinkInfo": {},
  "locations": [],
  "codeFlows": []
}
```

### 14.5 写入文件

最终执行：

```ts
FileUtil.writeJSONfile(
  path.join(Config.reportDir, 'report.sarif'),
  sarif,
  true,
)
```

生成：

```text
<reportDir>/report.sarif
```

## 15. 完整示例

假设源代码是：

```python
data = input()
eval(data)
```

### 15.1 Tree-sitter 阶段

生成 CST：

```text
module
├── assignment
│   ├── identifier: data
│   └── call: input()
└── call
    ├── identifier: eval
    └── argument: data
```

### 15.2 Visitor 阶段

转换为简化的 UAST：

```text
CompileUnit
├── VariableDeclaration
│   ├── Identifier(data)
│   └── CallExpression(input)
└── CallExpression
    ├── Identifier(eval)
    └── Identifier(data)
```

### 15.3 PythonAnalyzer 阶段

建立抽象值和引用关系：

```text
input() 返回值
→ Value A

变量 data
→ 指向 Value A

eval(data)
→ 参数为 Value A
```

### 15.4 Checker 阶段

规则识别：

```text
input()
→ source
→ 给 Value A 添加 taint

eval(...)
→ sink
→ 参数 Value A 携带 taint
→ 产生 finding
```

### 15.5 ResultManager 和 SARIF

Finding 首先保存到：

```text
findings.taintflow
```

随后转换为：

```text
Source: input()
→ Assignment: data = ...
→ Sink: eval(data)
```

并写入：

```text
report.sarif
```

## 16. 职责边界总结

| 层级 | 核心职责 | 不负责什么 |
| --- | --- | --- |
| `main.ts` | 启动进程、转交参数、捕获顶层异常 | 不解析代码，不分析漏洞 |
| `starter.ts` | 参数解析、生命周期编排、选择 Analyzer、输出结果 | 不实现 Python 语法转换 |
| Engine `parser.ts` | 多语言统一入口、文件读取、缓存和 UAST 后处理 | 不实现具体 Python 节点映射 |
| `python-ast-builder.ts` | Engine 与 Python UAST 包之间的适配 | 不逐节点构造 UAST |
| `parser-Python/src/index.ts` | 提供稳定的包级 `init()` / `parse()` API | 不实现主要转换逻辑 |
| `parser-Python/src/parser.ts` | 初始化 Tree-sitter、加载 grammar、源码转 CST | 不直接完成 CST 到 UAST 的全部映射 |
| `tree-sitter-python.wasm` | 根据 Python grammar 生成 CST | 不生成 YASA UAST，不做污点分析 |
| `parser-Python/src/visitor.ts` | CST 转换为统一 YASA UAST | 不做安全规则判断 |
| `PythonAnalyzer` | 建模、符号解释、抽象执行、Value 和 taint 传播 | 不定义最终报告格式 |
| Checker | 定义 source、sink、sanitizer 和安全判断 | 不负责整个程序的语义执行 |
| `ResultManager` | 分类收集 findings | 不决定具体漏洞检测逻辑 |
| Output Strategy | findings 去重、转换并写出 SARIF | 不参与 UAST 构造和污点传播 |

可以把整个系统概括成六句话：

```text
Tree-sitter：识别代码在语法上长什么样。
Visitor：把 Python CST 转换成统一 UAST。
PythonAnalyzer：模拟这些 UAST 的程序语义。
Checker：判断模拟过程中是否出现安全问题。
ResultManager：收集 Checker 产生的问题。
OutputStrategy：把问题转换成 SARIF 报告。
```
