# Python tree-sitter 重构交付记录

## 实现范围

已将 Python 的生产解析路径迁到 npm TypeScript Parser：
`源码 → tree-sitter-python WASM → Visitor → UAST → Engine 统一后处理`。
接口与 PHP 一致，先 `await init()`，再同步 `parse()`；Engine 的项目解析、
单文件内存源码、子进程 worker 均已接入。不再启动 Python/uast4py，
不再写临时源码或解析结果 JSON；依赖下载脚本也不再下载 uast4py。

旧 Python Visitor 和二进制发布 job 暂时保留，供差分测试和未迁移的消费者使用。
这不是删掉整个旧目录，也不代表完整 Python 语言兼容或跨平台发布验收完成。

主要入口：

- `uast/parser-Python/src/index.ts`：npm API。
- `uast/parser-Python/src/parser.ts`：WASM 生命周期、语法错误、BOM、旧软关键字兼容。
- `uast/parser-Python/src/visitor.ts`：旧 UAST 协议映射。
- `engine/src/engine/parser/python/python-ast-builder.ts`：Engine 适配层。
- `engine/test/python/test-python-tree-sitter.ts`：实际等待扫描完成的集成断言。

## 已执行验证

基于工作区固定版本：Engine `249420d17656988138831956babebae456bfa6e1`，
UAST `07e3823e56daaebe464626d7558e7fd2840674bf`。
本机为 macOS ARM64；旧解析器对照使用 CPython 3.14.4 和仓库原 Visitor。

| 检查 | 结果 |
| --- | --- |
| Parser TypeScript 构建 | 通过 |
| Parser 单测，启用旧实现对照 | 16/16 通过，无跳过 |
| 调试 f-string 专项差分 | 3 个样例含 UTF-8 位置，与旧实现完全一致 |
| xAST sast-python3 UAST 正文差分 | 800/800 完全一致，包括 loc 和 _meta |
| Engine TypeScript `--noEmit` | 通过 |
| Engine 新集成测试，启用旧实现对照 | 4/4 通过 |
| Engine no-init-dispatch 12 文件 | 新旧均 7 条检出，完整格式化结果和每一步污点链一致 |
| npm 包 | 已构建、打包并测试解包入口；非独立环境安装验收 |

xAST 本地检出版本为 `70e48aabac9b107c02bc46e97e7576fa81a0c4cf`，
来源为 `alipay/ant-application-security-testing-benchmark`。
800 文件验证的是原始 UAST 正文，不应等同于 800 文件的 Engine 全量检出对比。

历史 no-init-dispatch 文本预期中，`explicit_init_T.py` 的一段中间链路与
当前固定 Engine + 旧解析器的实际结果已有差异。未修改该预期文件：
新测试对历史预期检查逐文件检出数，并在独立进程中严格比较新旧实际完整链路。
旧实现仅在测试 runner 中通过 Python 调用，不进入生产路径。

额外用本机 CPython 3.14.4 标准库及其测试目录作语法覆盖探索：
1850 个文件中 1822 个解析成功，28 个明确报错；读取加解析约 11.67 秒，
初始化约 5.39 毫秒，进程 RSS 约 382 MiB。这包含故意无效语法的测试文件。
这些数字不是与旧实现的性能对比，也不证明成功解析文件的语义全部一致。

## 复现

先构建 Parser，再安装 Engine 的本地依赖。Python 仅用于可选对照测试。

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

不设置 `PYTHON_UAST_ORACLE` 时，差分单测会明确跳过，不能算作对照验证通过。
Engine 测试中的旧实现 runner 依赖本工作区的相邻 `uast` 目录。

## 兼容边界与发布前待办

- 保留旧协议的若干特殊映射及限制，详见 Parser README。
- 非 raw/bytes 的命名 Unicode 转义、3.14 template string
  暂不支持，明确抛出错误；相邻混合 f-string 的常量合并尚未全面对齐。
- grammar 对部分泛型默认值、星号类型表达式和特殊跨行属性存在缺口。
- 多生成器推导式、match guard 做了语义补全，仍需专项 Engine 检出回归。
- Engine 目前依赖 `file:../uast/parser-Python`，适合此双仓库工作区。
  独立发布 Engine 前须发布 Parser npm 包并将依赖改为正式版本。
- WASM 资源声明包含本地链接布局；尚未验证 Engine 的 pkg 独立可执行文件。
- 已添加三平台 Parser CI 和 npm 发布 job，但未执行远程 CI、发布 npm 或构建三平台二进制。
- 完整 xAST 检出对比、旧新耗时/峰值内存对比尚未执行。
