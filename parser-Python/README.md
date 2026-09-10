# Python UAST Parser

Python 源码 → `tree-sitter-python` WASM → TypeScript Visitor → YASA UAST。

新入口为 `@ant-yasa/uast-parser-python`，与 PHP Parser 使用相同的
`await init()` / 同步 `parse()` 接口。解析过程不启动 Python 或 `uast4py`，
不创建临时源码文件。旧 Python 实现保留在 `uast/`，用于兼容性对照。

## 构建与使用

```bash
npm ci --ignore-scripts
npm run build
npm test
```

`--ignore-scripts` 跳过 grammar 包的原生绑定安装，本 Parser 只加载其 WASM。
推荐 Node.js 22 或更新版本。

```ts
import { Parser } from '@ant-yasa/uast-parser-python';

const parser = new Parser();
await parser.init();
const ast = parser.parse('import os\nos.system(command)\n', {
    sourcefile: '/project/example.py',
});
```

- `init()` 支持重复、并发调用；初始化失败后可以重试。
- `parse()` 返回 `UAST.Node`（根节点为 `CompileUnit`），初始化前调用会报错。
- 无法解析或尚未映射的语法会抛出 `SyntaxError`；语法树错误附带文件/行号。
- 每次解析后释放语法树；临时变量编号按文件重置。
- `sourcefile` 可以在构造函数中设置，再由每次 `parse()` 覆盖。
- `version` 单独导出 npm 版本；`CompileUnit` 保留旧协议的
  `uri: null`、`version: null`、`languageVersion: '3.13'`。
  后者是兼容字段，不代表完整支持 Python 3.13/3.14 的全部语法。

## 验证

单测不需要 Python。设置 `PYTHON_UAST_ORACLE` 后，还会用旧 Parser
逐字段比较官方样例，包括位置和完整的类型注解 `CompileUnit`：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHON_UAST_ORACLE="$PWD/.venv/bin/python" npm test

npm run test:corpus -- /path/to/python/project
PYTHON_UAST_ORACLE="$PWD/.venv/bin/python" \
  npm run test:compare -- /path/to/xast/sast-python3
```

`test:corpus` 输出解析数量、失败详情、初始化耗时和读取/解析总耗时。
`test:compare` 比较完整 UAST 正文（不移除位置或元数据），差异时非零退出。
默认显示前 12 个失败文件，可通过 `DIFF_LIMIT` 调整。

## 兼容约定与范围

保留旧 Visitor 的列表/字典、关键字参数、`self`/`this`、构造器、装饰器、
类型注解、导入、赋值、切片、异常、异步语句和 match 模式映射。
bytes 的 JSON 值保持为字节数组；空 f-string 保持旧版的 `null` 表示。
普通 Python 标识符的列号使用 UTF-8 字节计数，以匹配 CPython。
f-string 文本片段位置与 CPython 3.14 对齐；旧版本 CPython 的片段范围可能不同。

单生成器推导式保留旧结构；多生成器/多条件推导式使用嵌套循环和条件，
避免旧实现将依赖的生成器放在同一层。match 的 guard 会保留为条件语句。
这些扩展须在后续检出回归中单独验证。

本包用于静态分析，不执行 Python，也不替代 Python 编译器的全部语义检查。
保留旧实现对 `for/while ... else`、`try ... else`、f-string 格式说明符等的
现有处理限制。`tree-sitter-python@0.25.0` 对部分较新的泛型默认值、
星号类型表达式以及特殊跨行属性语法仍会报告错误。
调试 f-string（`f'{x=}'`）保留标签文本、空白和表达式，并合并相邻文本片段。
命名 Unicode 转义（非 raw/bytes 的 `\N{...}`）和 Python 3.14 template string
（`t'...'`）目前明确报错，避免静默生成错误值。
相邻混合 f-string 的常量合并结构尚未与旧实现全面对齐。
UTF-8 BOM 会在解析前去除，延续旧 Engine 的处理方式。

`npm pack` 可生成本地 npm 包。CI 包含 Linux/macOS/Windows 测试配置；
本地验证不等同于三平台 CI 已执行。发布工作流已新增 Python npm job，
旧二进制发布流程暂时保留以兼容尚未迁移的 Engine。实际 npm 发布还需配置
该包的 trusted publisher，并推送正式版本标签。

## 旧解析器构建（仅用于对照）

### 安装依赖
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 使用示例

先从 spec 生成 Python 结构约束层：
```bash
cd ../specification
npm run generate-python-asttype
```

生成文件位置：
```bash
parser-Python/uast/asttype_generated.py
```

解析项目目录：
```bash
python3 -m uast.builder --rootDir /path/to/project --output ./output -j16 -v
```

解析单文件：
```bash
python3 -m uast.builder --rootDir /path/to/file.py --output ./output.json --singleFileParse True -v
```

### 打包为可执行文件（可选）

使用命令行：
```bash
python -m venv .venv
source .venv/bin/activate
pip install pyinstaller
pip install -r requirements.txt
pyinstaller --onefile --paths .venv/lib/python3.13/site-packages ./uast/builder.py
```

使用现有的 spec 文件：
```bash
pip install pyinstaller
pyinstaller builder.spec
```

打包后的使用示例：
```bash
./dist/builder --rootDir="/path/to/project" --singleFileParse=False --output="/path/to/output"
```
