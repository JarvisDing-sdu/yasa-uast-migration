# Yasa C 与 CodeGraph C：首轮调用图对比

日期：2026-11-06。最终评测对象是官方 Engine 提交 `59d2234`，叠加你们的 C 适配和一个已验证的 C worker 配置传递修复；并与 CodeGraph 最新正式发布版 v1.6.2 对比。这是独立评测适配版，不是官方已经发布的 C 支持版本。

## 结论与适用范围

在本轮样本内，Yasa C 的纯调用图模式与 CodeGraph 在两个小型真实项目的内部直接调用子集上打平；在独立构造的 C 语义样本中，Yasa C 的精确率与召回率更高。样本数量和项目规模有限，不能据此声称覆盖了所有 C 应用或大型工程。

- kilo：47 条参考调用边。Yasa 与 CodeGraph 均为 TP=47、FP=0、FN=0，精确率与召回率均为 100%。
- linenoise：144 条参考调用边。Yasa 与 CodeGraph 均为 TP=144、FP=0、FN=0，精确率与召回率均为 100%。
- 独立 C 语义样本：28 条参考调用边。Yasa 纯调用图模式 TP=26、FP=0、FN=2，精确率 100%、召回率 92.9%；CodeGraph TP=16、FP=2、FN=12，精确率 88.9%、召回率 57.1%。
- 补充配置：在同一语义样本上，Yasa 启用默认 C 分析包后为 TP=28、FP=0、FN=0。该结果与纯调用图模式分开记录。

## 版本必须区分

- 集成仓库：[JarvisDing-sdu/yasa-uast-migration@f106c11](https://github.com/JarvisDing-sdu/yasa-uast-migration/commit/f106c11a7a400bf94931fc7a9dcbc89997d3d429)。
- C 模块来源：[JarvisDing-sdu/yasa-engine@b8bea798](https://github.com/JarvisDing-sdu/yasa-engine/commit/b8bea798a322d363683d43237f1d10c1e85579fc)，2026-10-29 的 main 提交。该分支用于前一轮参考；最终数据已在下面的官方新底座上全部重跑。
- 实际运行的 UAST / C parser：[JarvisDing-sdu/yasa-uast@3f2141f9](https://github.com/JarvisDing-sdu/yasa-uast/commit/3f2141f93be48299c5908afbd6c8e8720bae431e)。
- CodeGraph：[正式发布版 v1.6.2](https://github.com/colbymchenry/codegraph/releases/tag/v1.6.2)，源码提交 `6560052a6f856855d3f71eee838fd66ccfa4285d`。本次未运行其 main 的未发布提交。
- 实际运行的 Engine 底座：[antgroup/YASA-Engine@59d2234](https://github.com/antgroup/YASA-Engine/commit/59d223494f1de37d4f3277848db241418bfcd068)。这是用户截图中的版本；原始提交没有 C 前端。评测在其独立副本上应用 `Yasa-latest-engine-C-adaptation.patch`，C parser 则固定为上述 UAST 提交。补丁 SHA-256 见结果 JSON 的 manifest。

集成仓库锁定的 Engine/UAST 提交分别为 `8cde2dc` 与 `e6dfd64`。锁定提交与组件各自 main 的 `b8bea798`、`3f2141f9` 在当时的代码树相同，差别是合并提交。官方上游和你们 Engine 分支有 56 个同路径文件内容不同，所以最终适配没有整体覆盖这些文件：C 模块保留，官方公共分析器、ValueRefMap、克隆、图结构、输出和内存护栏等保留新实现。官方 Python 前端及其初始化方式也保留。

独立审阅发现 C worker 未收到预处理配置。新增 12 文件回归在修复前全部选中错误分支，修复后全部选中正确分支。补丁只为 C 任务传递宏配置和项目头文件根目录。这个问题在三个原有评测样本中未触发，修复没有改变这些样本的指标。

## 统计口径

统计单位是去重后的内部函数调用对 `(调用方文件, 调用方函数, 被调方文件, 被调方函数)`。同一函数在多个位置调用同一目标只计一条边。两个文件中的同名 static 函数保留文件身份，头文件声明与唯一对应的实现定义对齐。

精确率 = TP / (TP + FP)；召回率 = TP / (TP + FN)。未解析的占位目标不算作已正确解析的内部调用，但其遗漏的参考边仍计入 FN。外部库函数、系统头文件实现、contains/imports 等非调用关系不在指标中。

真实项目取主实现文件中有定义的函数之间的直接调用：kilo 为 36 个函数，linenoise 为 85 个函数。参考关系由 Apple Clang 21.0.0 的 AST JSON 独立提取。它们不是两个项目全部跨文件和间接调用的总体准召率。

语义样本是一个独立的、可编译链接的 C 程序，包含 23 个函数、28 条参考边。20 条直接调用边经 Clang AST 逐项核对一致；8 条间接调用边在运行两种工具前人工标注，目标由程序中的固定赋值、固定数组下标等确定。样本覆盖跨文件调用、static 同名隔离、函数指针赋值及重绑定、参数回调、结构体字段、二级指针、函数指针数组、返回函数指针、递归、宏展开和条件编译。每类边界用例很少，只代表本次写法。

编译配置为 macOS、未知宏视为 undefined，`#if 0` 分支不属于该配置下的参考调用图。CodeGraph 保留了该分支的一条边；这是相对本次编译配置的 FP。若产品目标是所有配置的调用关系并集，应另定参考口径。

## 逐项发现

### Yasa 纯调用图模式

漏掉的两条边均位于 `callbacks.c`：

- `invoke → red`：函数指针通过参数传入；导出目标仍为 `callbacks.invoke.invoke_scope.f` 占位符。
- `cb_factory → blue`：调用返回的函数指针；外层调用目标仍为 `<callExp_16_32>` 占位符。对 `get_cb` 本身的直接调用已存在。

启用 `taint-flow-c-default` 并保留 `--dumpAllCG` 后，这两条边都能生成，语义样本达到 28/28。因此独立调用图接口的入口与上下文传播方式，是当前值得优先核查的接入点。

### CodeGraph v1.6.2

在语义样本中观察到两条额外边：

- `cb_array → red`：源程序调用 `list[1]`，确定目标是 blue。导出 metadata 为 `fn-pointer-dispatch`，经 `list[]` 关联了两个数组成员。
- `conditional_entry → enabled_leaf`：位于 `#if 0` 分支，本次编译配置下不可用。

12 条漏边由以下几组组成：

- 6 条跨文件直接调用：main 到 alpha_run、beta_run、cb_fixed、cb_parameter、cb_factory、conditional_entry。定义节点已存在，但这些调用引用在 `unresolved_refs` 中为 failed。原因尚未定位。
- 5 条间接调用：cb_fixed→red、cb_rebound→blue、invoke→red、cb_double→red、cb_factory→blue。
- 1 条宏展开后的调用：macro_entry→macro_leaf。

CodeGraph 在本样本的 static 同名隔离、结构体回调、字段区分和递归上也有正确结果。其实现包含 Tree-sitter 语法结构提取、名称解析和启发式关系合成；“纯字符串工具、精确率必然低很多”不是足够准确的描述，也不能替代实测。

## 运行命令

环境为 macOS arm64；两边使用的 Node 运行时为 v24.16.0。最终适配版有独立安装的依赖和更新后的 lockfile。C parser 原有 58 项测试通过；Engine 的 86 项既有 C 回归、新增 1 项 worker 回归及 142 项公共逻辑测试，共 229 项通过；`tsc --noEmit` 和 `tsc -p tsconfig.change-impact.json` 均通过。未运行依赖其他语言 SDK/外部靶场的全语言集成套件。

在 Engine 目录执行纯调用图模式：

```bash
node --import tsx src/main.ts \
  --sourcePath "$BENCH_SOURCE_ROOT" \
  --language c --cTarget macos --cUnknownMacros undefined \
  --checkerIds callgraph --dumpAllCG \
  --ruleConfigFile resource/example-rule-config/rule_config_c.json \
  --report "$BENCH_REPORT_DIR"
```

补充默认 C 分析模式，将 `--checkerIds callgraph` 替换为 `--checkerPackIds taint-flow-c-default`，其余参数不变。最终官方新底座的补充默认模式仅在 28 边语义程序上评测。报告不比较扫描速度。

CodeGraph：

```bash
CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1 CODEGRAPH_NO_DAEMON=1 \
  codegraph init --yes "$BENCH_SOURCE_ROOT"
```

Clang 参考提取：

```bash
clang -Xclang -ast-dump=json -fsyntax-only -Wno-everything \
  kilo.c > kilo-clang-ast.json
```

复现包中的 `evaluate_c_callgraph.py --help` 给出评分参数。它可以直接读取 Yasa 的 callgraph.json、CodeGraph 的 SQLite 数据库和 Clang AST / 手工 gold.json，重新计算本报告的指标。包内包含原始调用图、数据库、参考 AST、样本源码、日志、版本清单、适配补丁与评分脚本。`REPRODUCE.md` 说明如何检出官方底座和指定 UAST 提交、构建 parser、应用补丁并重新运行。local file 依赖本身不会自动下载 UAST，因此必须执行该检出步骤。

## 后续评测范围

官方最新 Engine + C 的移植、相关回归及同口径重跑已经完成，最终数字与之前 C 分支的小样本结果相同。补丁在本地评测副本生成，未向远端发布。

扩大评测时，应补充真实多编译单元 C 应用、构建配置、跨文件函数指针与外部库回调的独立参考关系。本轮不对大型 C 项目总体准召率或漏洞检测效果作结论。
