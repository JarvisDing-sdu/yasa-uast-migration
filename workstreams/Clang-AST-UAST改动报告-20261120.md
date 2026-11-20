# YASA Clang AST→UAST 改动报告

- 日期：2026-11-20
- 工作区：`D:\yasa_new\yasa-uast-migration`
- 主要实现：`D:\yasa_new\yasa-uast-migration\engine\src\engine\parser\c-family\clang-uast.ts`
- 当前状态：代码尚未提交

## 一、工作目标与范围

本阶段工作围绕 Engine 的 C-family 解析链路展开：

```text
源码与编译数据库
→ Clang 预处理
→ Clang 语义 AST
→ Clang AST→UAST 转换
→ UAST JSON
→ Engine 后续分析
```

工作重点在 Clang AST 到 YASA UAST 的结构映射和语义补充。没有把转换逻辑改成针对单个源文件的脚本，也没有按项目名、文件名、目录名或具体函数名编写补丁。Tree-sitter 路线继续保留，作为同一批编译配置下的独立对照。

## 二、新增和修改内容

### 1. AtomicExpr 内存序语义

补充原子操作的内存序解析：

- 支持整数字面量内存序。
- 支持 `memory_order_relaxed`、`memory_order_consume`、`memory_order_acquire`、`memory_order_release`、`memory_order_acq_rel`、`memory_order_seq_cst`。
- `compare_exchange` 保留成功和失败两个内存序候选。
- 写入 `_meta.clangAtomic.memoryOrder`。
- 无法确定内存序时保留 conversion diagnostic。
- C 和 C++ 原子操作均增加回归用例。

### 2. GNU 内联汇编

`GCCAsmStmt` 不再简单转为 unsupported：

- 保留输入操作数对应的 UAST 子表达式。
- 保存完整汇编原文。
- 保存 `volatile` 信息。
- 增加 `_meta.gnuAsm.modeled = false`，明确表示执行语义尚未建模。
- clobber 信息完整保留在汇编原文中。
- 带 `_meta.gnuAsm` 的 Sequence 不再被通用 flatten 规则错误展开。

### 3. 一般 goto

`GotoStmt` 增加：

- `_meta.goto`
- `_meta.gotoTargetOffset`
- `_meta.gotoKind`

并区分：

- `forward`
- `backward`
- `unknown`

保留 Noop 作为通用跳转占位，不再把一般 goto 直接计入 unsupported。该表示保留跳转目标信息，但不等同于完整控制流建模。

### 4. 依赖枚举值

对于模板或类型尚未实例化、无法静态折叠的枚举初始化：

- 保留原始表达式。
- 增加 `_meta.dependentEnumValue = true`。
- 不再丢弃枚举声明。
- 不再直接计入 unsupported。

### 5. EmptyDecl

空声明节点新增：

- Noop 输出
- `_meta.emptyDeclaration = true`

避免空声明被当成转换失败。

### 6. PredefinedExpr

补充 `__func__` 等预定义字符串表达式：

- 使用 Clang AST 提供的字符串值。
- 增加 `_meta.clangPredefined`。
- 保留源码位置和表达式结构。

### 7. ChooseExpr

补充 `__builtin_choose_expr`：

- 读取 Clang 已折叠的常量条件。
- 选择实际生效的 true/false 分支。
- 增加 `_meta.clangChooseExpr`。
- 条件无法判断时保留 `ConditionalExpression` 并显式标记。

### 8. 聚合数组隐式尾部

对于类似：

```c
struct Item items[4] = {{1}};
```

不再只报 unsupported，而是保留：

- 缺失元素数量
- 元素类型
- 默认初始化表达式
- `expanded: false`

对应元数据为 `_meta.clangImplicitArrayTail`。该表示避免展开巨大数组，同时保留结构信息。

### 9. AST 导出参数兼容

`engine/src/interface/compiler-dump.ts` 的通用白名单逐步补充：

- `-fno-strict-aliasing`
- `-mbranches-within-32B-boundaries`
- `-coverage`
- `-ffunction-sections`
- `-fdata-sections`
- `-fdiagnostics-color=always|auto|never`

这些参数主要影响代码生成、插桩、链接分节或诊断显示，不影响 Clang 对源码语法和 AST 的构建。

### 10. 测试与验收基础设施

补充和调整：

- AtomicExpr 的 C/C++ 参数顺序与内存序断言。
- GNU asm 操作数、原文和 `volatile` 断言。
- forward/backward goto 断言。
- dependent enum 元数据断言。
- EmptyDecl、PredefinedExpr、ChooseExpr、数组尾部断言。
- 构建参数白名单用例。
- c-family 测试主超时从 30 秒调整为 300 秒，以适应 drvfs 环境。
- 批量验收配置和结果分析脚本。

## 三、使用的库、工具与项目

### 1. 解析与转换核心

- **LLVM/Clang 23.1.5**：真实编译、预处理和 Clang AST JSON 生成。
- **YASA UAST 构造器**：使用项目已有的 `UAST.*` 节点构造能力，没有引入新的 UAST 转换框架。
- **TypeScript / Node.js**：Engine 编译和执行。
- **JSONStream**：流式读取大型 Clang AST JSON。
- **tsx**：开发状态下的 TypeScript 执行。
- **Mocha / Node assert**：parser 单测。
- **CMake / Ninja**：真实项目构建和 `compile_commands.json` 生成。

### 2. 双路线对照

- **Tree-sitter C/C++**：保留原有 `uast/parser-C` 和 `uast/parser-CPP` 路线，作为同批项目对照。
- 没有修改 Tree-sitter parser 源码。
- Clang 与 Tree-sitter 使用同一批 `compile_commands.json` 和同一官方批量 dump 入口。

### 3. 项目构建依赖

不同项目还使用了其自身构建依赖，例如：

- libgit2：OpenSSL、bundled zlib、pcre2、llhttp 等。
- libarchive：OpenSSL、系统 ACL/xattr/iconv 等检测依赖。
- libevent：OpenSSL、pthread 等。
- Mosquitto：cJSON、OpenSSL、pthread、内置 WebSocket 依赖等。

这些依赖仅用于真实项目构建，不属于 AST→UAST 转换逻辑本身。

## 四、真实项目验证结果

### 1. libuv

最终结果：

- 76/76 编译单元导出
- 76 个 `no_syntax_errors`
- 0 语法诊断
- 0 partial
- unsupported 为空

### 2. 五个 C 项目回归

覆盖 jansson、libpng、libuv、lz4、zlib，Clang 全部完整导出且无语法诊断。

Tree-sitter 对照中，libuv 有 2 个文件、共 10 条语法诊断，其余四个项目无语法诊断。

### 3. libgit2

- 固定提交：`42a89d7cc9374a19e72fa57011e5fe3a99c7b3bf`
- 237 个编译单元
- Clang：237/237 导出，全部 clean，0 partial
- Tree-sitter：237/237 导出，46 个 clean，191 个 syntax_errors，817 条语法诊断
- 两条路线函数定义记录均为 21,750
- 调用表达式记录：Clang 43,688；Tree-sitter 43,805

### 4. libarchive

- 固定提交：`432ab464725aa99c53de7572979bd9bbbf382ed1`
- 125 个编译单元
- Clang 和 Tree-sitter 均为 125/125 clean，0 语法诊断，0 partial
- 函数定义记录均为 2,697
- 调用表达式记录：Clang 12,225；Tree-sitter 12,373
- 首次运行暴露了 `-ffunction-sections` 和 `-fdata-sections` 参数入口问题

### 5. libevent

- 固定提交：`d82464a277d0f42703702c4dfd9af6af38595a83`
- 57 个编译单元
- Clang：57/57 clean
- Tree-sitter：52 clean、5 个 syntax_errors、10 条语法诊断
- 函数定义记录均为 2,820
- 调用表达式记录：Clang 11,551；Tree-sitter 11,507
- 首次运行暴露了 `-fdiagnostics-color=always` 参数入口问题

### 6. Mosquitto

- 固定提交：`7ae66ca5cf5e75dca18ba2f6cbdd21453c8e51a5`
- 非库类 C 应用项目，包含 broker、客户端和工具
- 197 个编译单元
- Clang 和 Tree-sitter 均为 197/197 clean，0 语法诊断，0 partial
- 函数定义记录均为 1,290
- 调用表达式记录均为 12,130

### 7. 单测与类型检查

- `npm run typecheck`：通过
- `test-clang-uast.ts`：36 passing
- `test-compiler-dump.ts`：9 passing
- `git diff --check`：通过

## 五、目标符合程度评估

从工程实施角度看，这一阶段已经形成了完整且可复现的验证链路：

- 真实项目先通过正式批量入口暴露问题；
- 问题能够被压缩为最小语言样例；
- 修复落在通用 AST 节点或通用构建参数上；
- 修复后重新跑单测和真实项目；
- Clang 与 Tree-sitter 使用同一批编译数据库进行结构级对照；
- 每个结论都有 manifest、统计文件或测试结果支撑。

因此，在“以 Clang AST 作为新的语义输入来源、以 AST→UAST 转换为重点、通过真实项目连续验收”的方向上，当前工作已经达到阶段性目标，并且没有采用按项目名称或具体函数打补丁的方式。

但严格来说，还不能称为绝对完美：

- curl、sqlite、jsoncpp、spdlog、ncnn 本轮没有在本机完整复跑，历史语料覆盖仍不完整。
- GNU asm、一般 goto、依赖枚举值、聚合数组尾部等节点已经保留结构或元数据，但其中一部分仍不是完整执行语义建模。
- 函数数和调用表达式数只能反映结构规模，不能直接代表调用图精确率或召回率。
- 当前代码仍未提交，验证结果和源码改动尚未形成正式版本记录。
- 不同项目暴露出的构建参数兼容问题仍可能继续出现，后续新增项目时应继续通过通用参数规则处理，而不是按项目放行。

整体评价：

> 工程路线、通用性约束和真实验收闭环已经达到较好完成度；语言语义覆盖仍属于逐步收敛阶段，尚不能据此宣称 Clang→UAST 已经完整覆盖 C/C++。

## 六、主要结果文件

### 源码与测试

- `engine/src/engine/parser/c-family/clang-uast.ts`
- `engine/src/interface/compiler-dump.ts`
- `engine/test/c-family/test-clang-uast.ts`
- `engine/test/c-family/test-compiler-dump.ts`

### libuv 最终结果

- `D:\yasa_new\benchmark\results\libuv-clang-dump-final2-20261117\manifest.json`

### 五项目最终对比

- `D:\yasa_new\benchmark\results\regression-20261118-final-clang\summary.json`
- `D:\yasa_new\benchmark\results\regression-20261118-comparison-final.json`

### libgit2

- `D:\yasa_new\benchmark\results\libgit2-clang-dump-final-20261118\manifest.json`
- `D:\yasa_new\benchmark\results\libgit2-comparison-20261118.json`

### libarchive

- `D:\yasa_new\benchmark\results\libarchive-acceptance-20261119-v3\summary.json`
- `D:\yasa_new\benchmark\results\libarchive-comparison-20261119.json`

### libevent

- `D:\yasa_new\benchmark\results\libevent-acceptance-20261120-v2\summary.json`
- `D:\yasa_new\benchmark\results\libevent-comparison-20261120.json`

### Mosquitto

- `D:\yasa_new\benchmark\results\mosquitto-acceptance-20261120\summary.json`
- `D:\yasa_new\benchmark\results\mosquitto-comparison-20261120.json`