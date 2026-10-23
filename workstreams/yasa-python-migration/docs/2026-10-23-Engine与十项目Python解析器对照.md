# YASA Engine 基础功能与 Python 解析器对照报告

测试日期：2026-10-23；环境：macOS arm64、Node.js 24.14.1、Python 3.13.13。

## 结论

新版 Tree-sitter Python 解析器已支持本次检查的 Engine 基础链路：帮助命令、单文件与目录 AST 导出、入口点收集、Python 污点规则扫描、SARIF 报告，以及调用链和 FastAPI 定向测试。对同一组 12 个 Python 样例文件，旧版与新版都识别 26 个入口点、产生 7 条告警；SARIF 文件逐字节相同。12 份 AST 在把新版 `_meta.decorators: null` 统一为旧版的 `[]` 后深度相同。

这还不足以认定两个解析器在真实代码上完全兼容。对 GitHub 上 10 个项目的 2,879 个 Python 文件，旧版解析成功 2,866 个，新版成功 2,847 个；其中 **20 个文件仅新版失败**。双方都成功的 2,846 个文件中，经过下文明确的最小归一化后，2,565 个 UAST 相同，**281 个仍有结构或取值差异**。这些差异未全部经过 Engine 规则级影响验证，应当作为迁移风险处理。

在两边都成功的相同文件上，直接解析及构建 UAST 的三轮耗时中位数为旧版 6.876 秒、新版 6.151 秒，新版少用约 **10.5%**。这项速度比较排除了源码读取、进程启动和 JSON 序列化。Engine 的端到端扫描另见下文，其旧版发布二进制与新版源码运行形态不同，不宜把全部加速归因于解析器。

## 对象、依据与范围

| 对象 | 本次固定版本或位置 |
| --- | --- |
| 原始 Engine | `/Users/infinite/Downloads/YASA-Engine`，Git `249420d17656988138831956babebae456bfa6e1`；基础测试调用该目录已有的 `yasa-engine-macos-arm64` 发布二进制，其运行横幅为 v0.3.2、build 20260927、commit `249420d` |
| 原始 Python 解析器 | `/Users/infinite/YASA-UAST/parser-Python`，仓库 Git `9d69d164b001f171bb0df0eed535dcb40c731c01`，即官方标签 **v0.2.19**；比较时调用其 Python `ast`/Visitor 源码，使用 Python 3.13.13 |
| 当前 Engine | 本工作区 `engine/` 子模块，Git `5d63b7914bf2b10168182d3e0b410a590189bbf7`；以 `node --import tsx src/main.ts` 运行 |
| 新 Python 解析器 | 本工作区 `uast/parser-Python/`，`uast/` 子模块 Git `7072a1f315bf8938287e49abe313203accfb377f`；`tree-sitter-python` 0.25.0、`web-tree-sitter` 0.26.8 与 TypeScript Visitor |
| 操作依据 | [用户提供的 YASA 操作手册](https://www.yuque.com/u22090306/bebf6g/evyf4chw26deq8xq)：`--help`、Python 规则、`--dumpAST`、SARIF、旧版 Python 的 `--uastSDKPath` |

测试只读取上述原始代码和项目源码。十项目比较选取克隆提交中 **全部 Git 跟踪的 `.py` 文件**，包括测试、格式化器输入和故意包含无效语法的夹具；因此“解析失败”须结合文件用途解释。没有通过运行项目自身测试来验证其业务行为。

旧版大语料比较直接调用 `~/YASA-UAST/parser-Python` 的原始 Visitor，而 Engine 基础测试调用原始发布二进制。为确认这两个旧版入口可比，另取 `no_init_direct_T.py` 对照了原始 Visitor 和旧 Engine `--dumpAST`：仅去除 Engine 后处理追加的 `nodehash`、函数/类名称及回填的 `loc.sourcefile` 后，两棵 AST 深度相同。该单文件核对不能证明二者对所有语法永远一致。

## Engine 基础功能

两侧使用相同的 `test/python/no-init-dispatch-cases` 目录（12 个文件、214 行）与 `test/python/rule_config_xast_python3.json` 中的 `taint_flow_test` 规则。旧版按手册指定 `--uastSDKPath /Users/infinite/Downloads/YASA-Engine/deps`；新版还用一个不存在的 SDK 路径执行成功，验证该 Python 链路不依赖外部 UAST 二进制。

| 检查 | 原始 Engine | 当前 Engine | 判断 |
| --- | --- | --- | --- |
| `--help` | 正常退出并列出选项 | 正常退出并列出选项 | 通过 |
| 单文件 `--dumpAST` | 生成 `CompileUnit` | 生成 `CompileUnit` | 归一化 `_meta.decorators` 后相同 |
| 目录 `--dumpAllAST` | 12 份 AST 和 `astList.json` | 12 份 AST 和 `astList.json` | 12 份 AST 归一化后相同；`astList.json` 原始字节相同 |
| Python 污点扫描 | 12 文件、26 入口点、7 告警、46 个 trace 步骤 | 相同 | SARIF 原始字节相同，SHA-256 `757336d2bcaa909bc7c5622655d37be6326e05e7c13da5a27f2ce57a6a5ba680` |
| 入口点导出 | 26 个 | 26 个 | 导出 JSON 原始字节相同 |
| 真实项目 AST 导出 | 本次未执行 | Requests 项目 37 个跟踪 `.py` 中导出 36 份 AST | 未写出 AST 的文件是 0 字节 `tests/testserver/__init__.py` |
| Requests 项目入口点导出 | 37 文件、12,069 行、532 个入口点 | 相同 | `entrypoints.json` 原始字节相同，SHA-256 `a8a383c4675c5e00a80ab323127c101b6e82dec6677d7b2fabb3ac12edce0672` |

新版附加测试：解析器单测 11 通过、5 跳过、0 失败；Engine 的 Tree-sitter 接入测试 3 通过、1 跳过；FastAPI `BackgroundTasks` 定向测试 6 通过，得到预期的 1 条 SARIF 告警；Python 调用链测试得到 4 条告警。`test-python-no-init-dispatch` 命令虽然运行结束并打印 7 条告警，但 Mocha 显示 `0 passing`，该测试脚本的异步注册方式没有提供可计数的断言，因此本报告以实际扫描和报告对照为依据。

同一 12 文件扫描各运行三轮：

| 指标 | 原始 Engine | 当前 Engine | 说明 |
| --- | ---: | ---: | --- |
| 实际耗时，三轮（秒） | 3.40 / 3.49 / 3.07 | 0.81 / 0.59 / 0.61 | 由 `/usr/bin/time -p` 记录 |
| 实际耗时中位数 | 3.40 秒 | 0.61 秒 | 约 5.6 倍 |
| Engine 内部 `parseCode` 中位数 | 2,720 毫秒 | 149 毫秒 | 约 18.3 倍 |
| Engine 内部总耗时中位数 | 3,161 毫秒 | 468 毫秒 | 两侧测量点与运行形态可能不同 |

旧版是已有的打包二进制，并调用 PyInstaller 外部 Python SDK；新版在 Node 进程内运行源码与 WASM。进程启动、打包形式、SDK 启动、缓存与统计口径均会影响这组端到端耗时。旧版在受限运行环境中曾因 `semctl` 权限失败，获准在正常系统权限下重跑后通过；这不是解析器失败。

对 Requests 固定提交另做了只收集入口点的完整项目运行（`--dumpEntrypoint`）：旧版实耗 18.84 秒、内部 `parseCode` 17,293 毫秒；新版实耗 2.11 秒、内部 `parseCode` 492 毫秒，两边输出的 532 个入口点 JSON 逐字节相同。该模式跳过逐入口的符号解释，所以不产生可用于告警对照的 SARIF。曾尝试让旧版执行 Requests 的完整规则扫描，但运行约两分钟仍只处理 170/532 个入口点，遂中止；本报告**不声称**已验证该真实项目的全量告警一致性。

## GitHub 十项目逐文件对照

下表项目名链接到本次实际克隆的固定 Git 提交，完整提交和文件清单也保存在同目录的[机器可读证据](./2026-10-23-Python解析器对照证据.json)中。每侧均对同一份 UTF-8 源码调用各自的解析器；`UAST 相同`只统计双方都解析成功、递归忽略 `loc` 并把 `_meta.decorators` 的 `null` 归一化为 `[]` 后，整个 JSON 树严格相同的文件。它不是 Python 运行时语义等价证明。

| 项目 | `.py` 文件 | 旧版成功 | 新版成功 | UAST 相同 | UAST 仍不同 | 旧版解析秒数 | 新版解析秒数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Black `1190eeb`](https://github.com/psf/black/commit/1190eeb39527e1ed81f9b35c931af66f31d05186) | 392 | 379 | 370 | 303 | 66 | 1.929 | 1.291 |
| [Click `2247b35`](https://github.com/pallets/click/commit/2247b35ea1c47c727d7a06e51fa280e12a863ff6) | 91 | 91 | 86 | 76 | 10 | 0.201 | 0.207 |
| [FastAPI `69ddc2b`](https://github.com/fastapi/fastapi/commit/69ddc2badf9da1123bba4d360225ae6b085985f6) | 1,216 | 1,216 | 1,216 | 1,194 | 22 | 0.989 | 1.077 |
| [Flask `d086db8`](https://github.com/pallets/flask/commit/d086db856be187255b8ec61ef409357393020f32) | 83 | 83 | 82 | 70 | 12 | 0.138 | 0.142 |
| [HTTPX `b5addb6`](https://github.com/encode/httpx/commit/b5addb64f0161ff6bfe94c124ef76f6a1fba5254) | 60 | 60 | 60 | 52 | 8 | 0.158 | 0.160 |
| [Jinja `5ef7011`](https://github.com/pallets/jinja/commit/5ef70112a1ff19c05324ff889dd30405b1002044) | 60 | 60 | 58 | 47 | 11 | 0.182 | 0.187 |
| [Pydantic `374a11d`](https://github.com/pydantic/pydantic/commit/374a11de11d95e014060204bb9dd1354c2fcbbbd) | 453 | 453 | 451 | 382 | 69 | 1.805 | 1.664 |
| [Pytest `4088e1a`](https://github.com/pytest-dev/pytest/commit/4088e1a84ef1cb8ba80aac4e75449459fc092c12) | 274 | 274 | 274 | 215 | 59 | 0.915 | 0.890 |
| [Requests `611c616`](https://github.com/psf/requests/commit/611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60) | 37 | 37 | 37 | 26 | 11 | 0.102 | 0.103 |
| [Rich `9d8f9a3`](https://github.com/Textualize/rich/commit/9d8f9a372cc5916fd4781fec207ced7ddac2f08f) | 213 | 213 | 213 | 200 | 13 | 0.451 | 0.441 |
| **合计** | **2,879** | **2,866** | **2,847** | **2,565** | **281** | **6.876** | **6.151** |

合计 25,624,741 字节源码；双方共同成功 2,846 个文件，共 25,161,828 字节。合计耗时是整个语料库每轮耗时的三轮中位数，不等于各项目中位数之和。FastAPI 在本机这组样本中略慢，因此“新版更快”是语料库总量结论，不是每个项目都更快。

### 解析覆盖与 UAST 差异

| 类别 | 文件数 | 解释 |
| --- | ---: | --- |
| 仅新版失败 | 20 | 14 个含 `\N{...}` 命名 Unicode 转义，新版明确拒绝；6 个被 Tree-sitter 报语法错误，但 Python 3.13 `ast.parse` 接受。14 个中包括生产文件 `black/src/black/comments.py`。其余仅新版失败文件均在测试或测试数据中。 |
| 两边都失败 | 12 | 主要是 Black 的故意无效语法、未来版本语法或模板字符串测试；不能算新版独有回归。 |
| 仅旧版失败 | 1 | Black 的 `remove_except_types_parens.py` 标注最低 Python 3.14，使用 PEP 758 的裸多异常 `except` 写法；旧版 Python 3.13 拒绝，新版 Tree-sitter 接受。 |
| 双方成功但原始 UAST 完全相同 | 0 | 新版 `_meta.decorators` 默认为 `null`，旧版为 `[]`。 |
| 仅统一装饰器默认值后完全相同 | 2,275 | 包括行列位置在内均一致。 |
| 再忽略 `loc` 后相同 | 另 290 | 仅剩行列位置差异，不能由此推断告警定位一定相同。 |
| 忽略上述两类差异后仍不同 | 281 | 有节点类型、值、数组长度或结构差异；占双方成功文件的 9.9%。 |

### 仅新版失败的 20 个文件：逐项定位

这 20 个文件的原始全文均可由 Python 3.13.13 `ast.parse` 直接解析。失败分为两层：14 个文件由新版 Visitor 在处理字符串时主动抛错；另外 6 个文件的 Tree-sitter 语法树已含 `ERROR`，新版 `parser.ts:80–86` 在调用 Visitor 前拒绝它们。下表列的是每个文件的首个有效命名转义；同一文件可能还有更多位置。14 个文件合计找到 53 处非 raw、非 bytes 的命名转义候选，所有位置都保存在机器可读证据中。

| 文件及首个位置 | 首个转义 | 字符串类型 | 同文件候选数 |
| --- | --- | --- | ---: |
| `black/src/black/comments.py:198` | `\N{NO-BREAK SPACE}` | 普通字符串；生产源码，另见 204 行 | 2 |
| `black/tests/data/cases/format_unicode_escape_seq.py:11` | `\N{ox}` | 普通字符串；名称使用小写 | 8 |
| `black/tests/data/cases/pep_701.py:105` | `\N{GREEK CAPITAL LETTER DELTA}` | f-string 正文 | 6 |
| `black/tests/data/cases/preview_long_strings.py:254` | `\N{LAO KO LA}` | 普通字符串 | 12 |
| `black/tests/data/cases/preview_long_strings__regression.py:519` | `\N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR}` | 普通字符串 | 4 |
| `click/tests/test_arguments.py:127` | `\N{COMBINING DOT ABOVE}` | 普通字符串 | 9 |
| `click/tests/test_basic.py:198` | `\N{SNOWMAN}` | 普通字符串 | 2 |
| `click/tests/test_deprecations.py:223` | `\N{KELVIN SIGN}` | 普通字符串 | 1 |
| `click/tests/test_options.py:1467` | `\N{KELVIN SIGN}` | 普通字符串 | 3 |
| `click/tests/test_utils/test_echo.py:14` | `\N{SNOWMAN}` | 普通字符串 | 1 |
| `flask/tests/test_json.py:53` | `\N{SNOWMAN}` | 普通字符串 | 1 |
| `jinja/tests/test_lexnparse.py:96` | `\N{HOT SPRINGS}` | 外层普通 Python 字符串，内容是 Jinja 模板 | 1 |
| `jinja/tests/test_regression.py:763` | `\N{FORM FEED}` | 普通字符串；名称是 Unicode 别名 | 1 |
| `pydantic/pydantic-core/tests/serializers/test_string.py:48` | `\N{GREEK SMALL LETTER ALPHA}` | 普通字符串 | 2 |

原因已定位到 `uast/parser-Python/src/visitor.ts:1054–1071`：`string()` 的 `decode()` 对非 raw 字符串遇到 `\N{...}` 就抛出 `Named Unicode escapes are not supported`。现有 `tests/parser.test.ts:15–20` 还把这项拒绝写成了预期测试。旧版通过 CPython 解析，Visitor 接收已经解码的 `ast.Constant.value`。本次 Python 3.13 的 Unicode 数据版本为 15.1.0；例如大小写不同的 `\N{ox}` 和 `\N{OX}` 都能解码，`\N{FORM FEED}` 也能按别名解码。仅在临时副本中把这些转义换成对应字符后，**14/14 个完整文件均能被新版解析**；这支持该分支是它们的解析阻断点，但不证明修复后的 UAST 已完全等价。

其余 6 个文件都在测试或测试输出夹具中，逐文件原因如下：

| 文件 | 真正触发的有效 Python 语法 | 新版错误提示 | 已定位的原因 |
| --- | --- | --- | --- |
| [Black `expression.py:160`](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/expression.py#L160) | `g = 1, *"ten"`，元组右侧展开字符串 | 161:1 `ERROR` | `list_splat_pattern` 只允许标识符等有限形式，表达式位置也错误复用该规则；错误恢复把提示推到下一行。 |
| [Black `preview_type_param_defaults_string_split.py:2`](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/preview_type_param_defaults_string_split.py#L2) | `def func[*Ts = Set["..."]]():` | 2:10 `ERROR` | `type_parameter` 规则没有 Python 3.13 的类型参数默认值分支。 |
| [Black `preview_unpacking_parens.py:82`](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/preview_unpacking_parens.py#L82) | `*(a), (b) = 1, 2` | 82:5 `ERROR` | 星号赋值目标规则不接受带括号的名称。 |
| [Black `preview_unpacking_parens_multiline.py:21–23`](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/preview_unpacking_parens_multiline.py#L21) | `[*(rest), last] = values`，其中 `rest` 跨行 | 23:10 `ERROR` | 与上一项相同；跨行布局改变了错误恢复位置。 |
| [Black `type_param_defaults.py:3`](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/type_param_defaults.py#L3) | `type A[T=int] = float` | 3:8 `ERROR` | 同一 `type_parameter` 规则缺少默认值语法；后续还有星号参数默认值。 |
| [Pydantic `frozen_field.py:22–24`](https://github.com/pydantic/pydantic/blob/374a11de11d95e014060204bb9dd1354c2fcbbbd/tests/mypy/outputs/mypy-plugin_ini/frozen_field.py#L22) | 类内缩进的 `@property` 与 `def` 之间有一行顶格注释 | 22:5 `ERROR` | Tree-sitter 把装饰器从类代码块中分离；把临时副本中的注释缩进后可解析。更精确的外部 scanner 分支仍需调试。 |

这 6 个完整文件与对应最小片段均通过 Python 3.13.13 `ast.parse`，但原始 Tree-sitter 0.25.0 语法树含错误节点。已在本机 `tree-sitter-python/grammar.js:469–474` 看到类型参数规则缺少 `=` 默认值，在 `:685–688` 看到星号目标只接受标识符、下标或属性；右侧展开还涉及 `:721–748` 把此目标规则用作表达式。Pydantic 案例定位为装饰器与顶格注释的布局问题，具体是 grammar 还是 external scanner 的哪一分支尚未确定。修复语法规则或升级语法包后，仍须检查 Visitor 对新节点的 UAST 映射。

### 双方可解析时的 UAST 差异

对 281 个文件按**第一个非位置差异**做互斥分类：字符串及 f-string 拼接树 121、临时标识符编号或 Unicode 标识符归一化 27、异常处理结构 22、数组长度 54、节点类型 52、参数默认值 3、`tuple[()]` 类型参数 1、操作符空格归一化 1。其中 160 个文件位于库源码目录，121 个位于测试、文档、脚本或示例目录。这种分类帮助定位问题，不表示一个文件只有一处差异，也不表示 281 个差异都是错误。逐文件的首几个差异路径保存在机器可读证据中。

已核实的真实源码例子：

- [Black `src/black/comments.py`](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/src/black/comments.py) 的命名 Unicode 转义令新版整文件解析失败；该文件是生产源码。
- [Pydantic `_internal/_config.py`](https://github.com/pydantic/pydantic/blob/374a11de11d95e014060204bb9dd1354c2fcbbbd/pydantic/_internal/_config.py) 的联合类型参数，旧版展开为 3 个 `typeArguments`，新版为 2 个且第二项嵌套 `Union`。
- [FastAPI `routing.py`](https://github.com/fastapi/fastapi/blob/69ddc2badf9da1123bba4d360225ae6b085985f6/fastapi/routing.py) 的位置仅限 `self` 方法，新版额外生成 `self=ThisExpression` 声明，相关方法体长度从旧版 8 变为新版 9。
- [Requests `compat.py`](https://github.com/psf/requests/blob/611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60/src/requests/compat.py) 的 `except` 代码块，旧版在 `body` 中保留一层数组，新版直接放 `VariableDeclaration`。
- [Rich `logging.py`](https://github.com/Textualize/rich/blob/9d8f9a372cc5916fd4781fec207ced7ddac2f08f/rich/logging.py) 的裸 `except:`，旧版首个参数为 `null`，新版生成了 `VariableDeclaration`。
- [Flask `templating.py`](https://github.com/pallets/flask/blob/d086db856be187255b8ec61ef409357393020f32/src/flask/templating.py) 的 `tuple[...]` 联合类型注解，旧版是带类型参数的 `DynamicType`，新版成为 `MemberAccess`/`Sequence`，类型信息未按同一 UAST 结构保留。[Pydantic `functional_serializers.py`](https://github.com/pydantic/pydantic/blob/374a11de11d95e014060204bb9dd1354c2fcbbbd/pydantic/functional_serializers.py) 的 `Callable[...] | Callable[...]` 也从旧版 `DynamicType(Union)` 变成新版 `BinaryExpression('|')`。
- [Pytest `pytest_rerunfailures_integration.py`](https://github.com/pytest-dev/pytest/blob/4088e1a84ef1cb8ba80aac4e75449459fc092c12/testing/plugins_integration/pytest_rerunfailures_integration.py) 中合法的 `type(self).first_time = False`，Tree-sitter-python 0.25.0 未报错却给出 `type_alias_statement`，新 Visitor 输出 `ClassDefinition`；旧版输出 `AssignmentExpression`。这是会改变赋值数据流建模的明确误映射。
- [Black 的 `with (CtxManager() as example):` 夹具](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/parenthesized_context_managers.py#L2)与 Pytest 类型检查夹具中，旧版保留调用和变量绑定，新版输出 `Noop`，会丢失该上下文表达式。
- [Black 的 Unicode 标识符夹具](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/tricky_unicode_symbols.py#L2)中，旧版按 CPython 规则把 `µ` 规范化为 `μ`，新版保留 `µ`，可能影响名称匹配。

并非所有差异都是新版退步：19 个含位置仅限 `self` 的文件里，旧版漏建 `self` 声明，新版补上；另有 3 个参数默认值差异源于旧版漏掉位置仅限参数的默认值。新版也保留了[部分 `match` guard](https://github.com/psf/black/blob/1190eeb39527e1ed81f9b35c931af66f31d05186/tests/data/cases/if_guard_inside_case.py#L8)，并正确嵌套多层推导式。字符串分段和临时标识符编号也可能只是表示变化。上述确定的误映射是否改变具体 Engine 告警，仍需针对受影响节点设计规则并对照 SARIF；本次 12 文件规则样例没有覆盖所有这些语法。

## 解析效率与资源占用

独立解析器计时在两侧预读同样的 UTF-8 源码，先预热 100 个文件，然后各运行三轮；每个文件只计解析及 Visitor 构建 UAST，不计源码读取、进程启动、JSON 序列化。Python 端为 CPython `ast.parse` 与原 Visitor，Node 端为 Tree-sitter WASM 与新 Visitor。时间不是同一种运行时的单模块微基准。

| 样本 | 旧版三轮（秒） | 新版三轮（秒） | 中位数 | 旧/新比值 |
| --- | --- | --- | --- | ---: |
| 共同成功的 2,846 个文件 | 6.969 / 6.876 / 6.875 | 6.295 / 6.151 / 6.045 | 6.876 / 6.151 秒 | 1.12 倍 |
| 全部 2,879 个文件，含失败尝试 | 6.990 / 7.011 / 7.001 | 6.517 / 6.520 / 6.662 | 7.001 / 6.520 秒 | 1.07 倍 |

共同成功样本预加载源码后的进程峰值 RSS：旧版约 309 MiB，新版约 461 MiB；全量样本旧版约 314 MiB、新版约 510 MiB。这里包含 CPython/Node 运行时、预加载源码、Visitor 输出以及 WASM，不能据此给出解析器自身的内存开销结论。

### 与此前 Markdown 性能记录、官方 v0.2.19 的关系

此前文档使用的旧官方 UAST 基线是 **v0.2.18**（`07e3823`）；本次直接比较的原始 Python Visitor 是 **v0.2.19**（`9d69d16`）。这里的 v0.2.19 是旧版 YASA-UAST 的发布标签，不是新版所用 `tree-sitter-python` 的版本；新版语法包仍是 0.25.0。进一步核对发现，原始 Engine `deps/uast4py/uast4py` 的 SHA-256 `c34abf48bcde27673ff3d8dbe3d781e8cf2b426f520668706e05f9f2da9888e1` 与[官方 v0.2.19 macOS ARM64 资产](https://github.com/antgroup/YASA-UAST/releases/download/v0.2.19/uast4py-mac-arm64)摘要相同，故本次原始 Engine 使用的外部 SDK 也为 v0.2.19；但下面的版本性能实验仍只对**直接调用的原始 Visitor 源码**成立，不能视为二进制计时。

| 既有记录 | 旧侧与新侧所计内容 | 已记录的结果 | 对本次的可比性 |
| --- | --- | --- | --- |
| [xAST 800 文件](xAST-检出与性能对比.md#纯解析800-文件) | 旧 v0.2.18 官方二进制墙钟含启动、等待及写出 800 个 JSON；新版读取并解析但不写文件 | 旧 12.69 秒、新 136.8 毫秒，约 92 倍；旧二进制 CPU 时间约 1.75 秒 | 运行形态不同，92 倍不能视作解析算法本身的倍数；[2026-10-23 复测](2026-10-23-xAST性能与检出复测.md)发现旧二进制处理空目录也需 10–20 秒 |
| [xAST 606 文件](xAST-检出与性能对比.md#本机性能) | Engine `parseCode`；旧侧经批量 CPython 子进程 oracle | 旧 1,825 毫秒、新 520 毫秒，约 3.51 倍；总墙钟旧 4,020、新 2,713 毫秒 | 计入 Engine 集成、进程通信及 JSON 转换，与本次进程内逐文件解析不同 |
| [OWASP 1,230 文件](OWASP-Python-旧新回归.md#本机性能) | Engine `parseCode`；旧侧经批量 CPython 子进程 oracle | 旧 14,074 毫秒、新 1,605 毫秒，约 8.77 倍；总墙钟旧 69,752、新 60,697 毫秒 | 语料和 Engine 分析负载也不同，解析阶段倍数与总扫描收益不能混用 |
| [PyTorch 122 文件](emitter/PyTorch真实源码-解析与还原.md#性能观察非-e-项最终结论) | 每文件分别启动旧二进制和新版导出器 | 旧 84.49 秒、新 13.20 秒，约 6.4 倍 | 主要用于功能摸底，包含反复启动与导出开销 |
| 本次十项目共同成功的 2,846 文件 | 两侧预加载源码、预热后，只计解析与 Visitor 构建 UAST | 旧 v0.2.19 为 6.876 秒、新 6.151 秒；新版少用约 10.5% | 是本次最接近直接解析的口径，但运行时不同，且不是逐进程交替的严格微基准 |

为单独检验官方版本变化，另用**完全相同的 2,846 个文件**、Python 3.13.13 和同一计时程序测旧 Visitor；每进程预热 100 文件，排除读取、启动与序列化，运行顺序为 v0.2.18-A → v0.2.19-A → v0.2.19-B → v0.2.18-B。每个进程跑三轮：

| 旧 Visitor 版本或临时消融 | 逐轮解析秒数 | 汇总 |
| --- | --- | --- |
| v0.2.18-A | 6.965 / 6.477 / 6.409 | 两个 v0.2.18 进程合计六轮中位数 **6.443 秒** |
| v0.2.18-B | 6.354 / 6.405 / 6.490 | 同上 |
| v0.2.19-A | 6.884 / 7.167 / 7.341 | 两个 v0.2.19 进程合计六轮中位数 **7.064 秒** |
| v0.2.19-B | 7.489 / 6.879 / 6.961 | 同上 |
| v0.2.19 临时副本，仅把 `Meta.decorators` 默认值改回 `None` | 6.245 / 6.729 / 6.413 | 三轮中位数 6.413 秒；仅是辅助归因，不是正式发布版本 |

此语料中 v0.2.19 的旧 Visitor 比 v0.2.18 **慢约 9.6%**。`v0.2.18..v0.2.19` 的运行时代码差异主要是 `asttype_generated.py` 把每个 `Meta.decorators` 的默认值从 `None` 改为 `field(default_factory=list)`，以及 `visitor.py` 给合成构造函数显式设空列表；没有改动语法解析算法。临时消融的计时接近 v0.2.18，支持频繁创建空列表是这组数据中变慢的主要来源，但单次消融和系统负载波动不构成跨机器保证。该默认值变化还解释了本次原始 UAST JSON 直接严格比较时全部不同；报告先把 `null` 与 `[]` 归一化，之后仍有 281 个文件存在非位置差异，不能归咎于该元数据默认值。

因此，**升级到 v0.2.19 不会解释“新版加速优势缩小”**：在本次同条件旧侧实验里，它反而使旧版变慢。过去较大的倍数主要来自不同语料、旧二进制调用时的固定开销和文件写出、子进程通信，以及 Engine 计时范围；本次 10.5% 是排除这些开销后、在真实项目共同成功文件上的解析与 UAST 构建比较。上述历史 Markdown 的镜像副本没有当作独立测量重复计数。原始轮次也收录在同目录机器可读证据的 `version_audit` 字段。

## 判断与后续处理重点

1. Engine 的已测基础功能可以运行，控制样例的实际告警和入口点与旧版一致。
2. 若迁移验收要求与原解析器同样覆盖 Python 3.13 源码，应优先处理 `\N{...}` 命名 Unicode 转义和 6 个仅新版拒绝的有效语法文件；其中前者已经影响 Black 生产源码。
3. 如依赖 UAST 协议的精确形状，应明确 `_meta.decorators`、`loc`、`except`、联合类型、`self` 注入及字符串拼接等差异的预期表示，并用 Engine 检测结果回归。尤其要修正赋值被识别成类型别名、`with` 绑定丢失，以及部分类型注解结构退化。当前不能把 2,565/2,846 的结构相同率解释为 90.1% 的运行时语义正确率。
4. 性能总量有改善，但 FastAPI 等个别项目未受益；落地前应在目标代码库的实际扫描流程中复测耗时与峰值内存。

## 复核方法

控制样例的完整扫描可分别从两个 Engine 目录运行；报告目录可换成其他临时位置：

```bash
cd /Users/infinite/Downloads/YASA-Engine
./yasa-engine-macos-arm64 \
  --sourcePath /Users/infinite/Downloads/YASA-Engine/test/python/no-init-dispatch-cases \
  --language python --analyzer PythonAnalyzer --checkerIds taint_flow_test \
  --ruleConfigFile test/python/rule_config_xast_python3.json \
  --uastSDKPath /Users/infinite/Downloads/YASA-Engine/deps \
  --report /private/tmp/yasa-check-old --workerCount 1

cd /Users/infinite/Downloads/yasa-uast-migration/engine
node --import tsx src/main.ts \
  --sourcePath /Users/infinite/Downloads/YASA-Engine/test/python/no-init-dispatch-cases \
  --language python --analyzer PythonAnalyzer --checkerIds taint_flow_test \
  --ruleConfigFile test/python/rule_config_xast_python3.json \
  --uastSDKPath /missing-legacy-sdk \
  --report /private/tmp/yasa-check-new --workerCount 1
```

在两条命令末尾改用 `--dumpEntrypoint` 可快速复核入口点导出。十项目语料按表中固定提交检出，通过 Git 跟踪的 `.py` 路径选取。旧解析端先运行 Python 3.13 的 `ast.parse`，必要时调用原项目的 `_try_compat_parse`，再由 `UASTTransformer` 构造 `CompileUnit`；新端运行 `Parser.init()` 与 `Parser.parse(source, {sourcefile})`。每个源码以相同的 UTF-8 文本分别输入，记录成功状态和完整 UAST JSON，然后按文中定义归一化并深度比较。两侧性能测试均预读相同源码、预热 100 文件、遍历三轮，每轮汇总单文件解析耗时。

## 证据与改动

同目录[机器可读证据](./2026-10-23-Python解析器对照证据.json)保存 10 个固定提交、逐文件成功/失败与首个 UAST 差异、20 个仅新版失败文件的逐项定位及三轮解析耗时。临时的完整扫描输出保存在 `/private/tmp/yasa-engine-baseline/`、`/private/tmp/yasa-engine-new/`，语料库和比较原始结果保存在 `/private/tmp/yasa-corpus/`；这些临时目录可能随系统清理而消失。

本次没有改动原始 Engine、原始 UAST 或当前 `engine/`、`uast/` 的受版本控制源码。工作区只新增本报告和上述证据文件。测试期间生成了被 Git 忽略的编译产物、日志和报告。当前工作区原有的 `.DS_Store`、`.gitignore`、`workstreams/README.md` 及 PowerPoint 相关未提交变更在测试前已存在，本次未编辑。原始 Engine 目录中已有的 `package-lock.json`、`src/interface/starter.ts` 修改及 `uast.json` 未跟踪文件也保持原状。
