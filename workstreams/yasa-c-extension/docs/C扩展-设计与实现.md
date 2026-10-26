# C 语言扩展：设计与实现

本文说明 YASA 的 C 语言支持是怎么实现的，以及相对于之前那版 C 原型（`sijie52/parser-c`）改了什么、为什么改。验收数据见 [四项验收报告](C扩展-四项验收报告.md)。

## 1. 整体链路

```text
.c/.h 源码
  │  uast/parser-C：tree-sitter-c (WASM) → CST → visitor → UAST
  │      按编译配置预处理（宏顺序、#if 求值、头文件宏）、ERROR 区域恢复
  ▼
UAST (CompileUnit, language = 'c')
  │  engine/src/engine/analyzer/c：CAnalyzer
  │      跨文件链接、指针别名、聚合类型、库函数输出参数模型
  ▼
符号执行 + 污点传播
  │  engine/src/checker/taint/c：taint_flow_c_input
  │      entrypoint = 调用图根函数（含 main）；source/sink 来自 ruleconfig
  ▼
SARIF 告警（含 codeFlow 污点路径）
```

和 Python、PHP 一样，parser 只负责把源码准确翻译成 UAST，语言语义放在 Engine 的分析器里。

## 2. parser-C

代码：`uast/parser-C/src/parser.ts`、`uast/parser-C/src/macros.ts`。在原型的基础上修改，保留了它“照搬 parser-PHP”的整体结构。

### 2.1 修复的原型缺陷

| 问题 | 原型表现 | 原因 | 修复 |
| --- | --- | --- | --- |
| 每条声明多一个假变量 `_` | `int x = 1;` 产生 `_ = null` 和 `x = 1` 两个声明 | 用 `!==` 比较 tree-sitter 节点；web-tree-sitter 每次返回新包装对象，比较永远不等，类型节点被当成声明符 | 改用 `childrenForFieldName('declarator')`，节点比较用 `id` |
| `#if/#ifdef/#ifndef` 包着的代码整段丢失 | 头文件保护里的函数全部消失 | 预处理条件块直接转成 `Noop` | 保留所有分支（静态分析无法知道编译配置） |
| 数字字面量错误 | `0x1F`→1，`010`→10，`0xFFUL`→字符串 | 后缀剥离把十六进制 `F` 当后缀；八进制没处理 | 按 C 规则解析十/十六/八/二进制与浮点，超过 2^53 保留原文 |
| 字符串转义未解码 | `"a\n"` 存成 `a\` + `n` | 直接去掉引号 | 按 `string_content` / `escape_sequence` 子节点逐个解码 |
| `"a" "b"` 未处理 | 变成未处理节点 | 没有 `concatenated_string` 分支 | 合并为一个字面量；夹着宏（如 `PRIu64`）时用 `+` 连接 |
| `typedef` 未处理 | 变成未处理节点 | 无分支 | 匿名结构体按别名命名；其它 typedef 记录在 `_meta.typedef` |
| `*p = x` 整个文件崩溃 | uast-spec 校验器拒绝 `DereferenceExpression` 作为左值 | spec 的 LVal 不含解引用 | 先用占位符构建再替换左值 |
| 一个语句出错整个文件失败 | 无 | 无容错 | 语句级容错：出错的语句降级为带 `_meta.buildError` 的 `Noop` |
| 语法错误静默吞掉 | 解析失败也不知道 | 不检查 `ERROR` 节点 | 记录到 `CompileUnit._meta.parseErrors`；`strict: true` 时抛错 |
| 声明符类型顺序反了 | `char *xs[4]` 被当成“指向数组的指针” | 递归方向错误 | C 声明符由内向外读取 |
| 每个节点存整段源码文本 | 大文件 UAST 体积随文件大小平方增长 | `_meta.origin.text` | 只保留节点类型 |
| 测试读写死路径 | 换电脑就跑不了 | `/home/dys1013/...` | fixture 放进仓库 |

### 2.2 新增能力

- **预处理（`src/macros.ts` 的 `MacroEnvironment`）**：在 tree-sitter 解析之前，像预处理器一样按行顺序扫描一遍本文件及其 `#include` 的头文件：
  - `#define`/`#undef` 从所在位置起生效，每个宏名保存一条“位置 → 可能的定义”时间线，使用处只看到当时有效的定义（使用在定义之前不展开、`#undef` 后恢复为普通函数调用、重定义取新值）；
  - `#if`/`#ifdef`/`#elif`/`#else` 在编译配置下三值求值（真/假/未知）：配置排除的分支在源码中替换为空格（偏移和行号不变），tree-sitter 只解析可能参与编译的代码；配置未决定的分支全部保留，分支中的函数/变量定义标记 `_meta.conditional`；
  - 未决定的条件之后，宏的可能定义是各可能分支结果的并集；使用处有多个可能定义（或可能不是宏）时，展开为以 `__preprocessor_choice__`（分析中视为未知）为条件的三目表达式/if 语句，每种展开都会被分析；
  - `#include "x.h"` 读取头文件（依次查找包含者目录、`--cIncludeDir`、项目根目录；`<x.h>` 只查 `--cIncludeDir`），头文件中的宏在 `#include` 处生效；包含的头文件列表记录在 `CompileUnit._meta.includes`；
  - 编译配置显式输入（Engine 命令行）：`--cDefine A,B=2`（-D）、`--cUndefine X`（-U）、`--cTarget linux|macos|windows|none`（目标平台预定义宏，默认 `linux`，即 Linux 上的 gcc/clang）、`--cUnknownMacros cover|undefined`。默认 `cover` 表示“覆盖多个配置”：代码和配置都没有决定的名字（如 `FEATURE`）按未知处理，`#ifdef FEATURE` 两侧都分析；`undefined` 表示“给定编译配置”：按 C 标准视为未定义，只分析一种配置；
  - 宏替换支持 `#x`、`a ## b`、`__VA_ARGS__`；展开文本重新解析成语句或表达式，位置改写为使用处，并防止递归展开。真实 C 代码与 Juliet 大量通过宏调用 sink（`EXECL(...)`），不展开就几乎检不出。
- **初始化列表带键**：数组按下标、已知结构体按字段名生成 `ObjectExpression`，使 `arr[1]`、`p.safe` 读到正确的项；未知结构体保持原来的 `TupleExpression`。
- **联合体**：同一个 union 变量的所有成员映射到同一个存储槽 `<union>`。
- **ERROR 区域恢复**：tree-sitter 遇到无法识别的宏时会生成跨越上千行的 `ERROR` 节点；其中完整的函数、声明、`#if` 块会被恢复出来。SQLite 的函数保留率因此从 96.7% 提高到 100%。
- **其它**：`switch` 中被 `#ifdef` 包着的 `case`、GNU 语句表达式 `({ ... })`、`__attribute__` 语句、`extern "C"` 块、`sizeof(type)`、复合字面量、函数原型不再遮蔽同名函数定义。

## 3. Engine 接入

### 3.1 注册

| 位置 | 改动 |
| --- | --- |
| `package.json` | `@ant-yasa/uast-parser-c: file:../uast/parser-C`（与 Python 相同的本地链接方式），打包资源加入 `tree-sitter-c` 的 wasm |
| `src/engine/parser/c/c-ast-builder.ts` | 异步初始化 WASM、同步 `parseSingleFile`，与 PHP 相同 |
| `parser.ts` / `parser-core.ts` / `parser-worker.ts` | 注册语言 `c`，文件模式 `**/*.c`、`**/*.h` |
| `src/interface/starter.ts` | `--language c`、`CAnalyzer`、扩展名 `.c/.h` |
| `resource/checker/*.json` | checker `taint_flow_c_input`、规则包 `taint-flow-c-default` |
| `resource/example-rule-config/rule_config_c.json` | 默认 source/sink |

### 3.2 CAnalyzer（`src/engine/analyzer/c/common/c-analyzer.ts`）

以 PHP 分析器的项目扫描骨架为基础，按 C 的语义补充：

| 语义 | 处理 |
| --- | --- |
| 声明类型 | `c-types.ts`：按词法作用域给每个变量引用标注声明类型（`_meta.cType`），登记 struct/union 字段类型和 typedef，供按值复制与指针模型使用 |
| 链接 | 非 `static` 的函数和文件级变量放进 topScope，所有文件共享；`extern` 声明不再创建同名局部变量；头文件中的 `static`（inline）函数属于包含它的每个编译单元：按 `CompileUnit._meta.includes` 放进各 .c 的模块 scope，不同头文件中同名的 static 函数互不覆盖（topScope 只留一份给无法解析 include 的编译单元）；配置未决定的 `#if` 分支中同名函数的多份定义保存为并集，调用时每份都执行，而不是取第一个 |
| `#include` | 不做模块导入（宏与头文件 static 函数已在解析/链接阶段处理） |
| 指针 | 区分存储位置、地址和值：标量/指针变量的 `&x` 是独立的地址值，记录它指向的位置；`*e = v` 写入 `e` 当前值所指向的位置，`*e` 读取该位置的当前值，因此 `**r = v`、`***s = v`、`*r = &o` 后的重绑定、`char ***` 输出参数、`&s.a` 指向字段都按位置逐级解析。struct/数组的存储就是其对象本身，`&s` 仍是该对象；指向未知存储（参数、堆）时退回为写指针变量本身 |
| 聚合类型 | 未初始化的结构体/数组局部变量初始化为空对象；多级写入 `g[1][0] = x` 前先建出中间层。struct 按值复制（`struct S b = a`、`b = a`、按值传参、`*ps = b`）：每个字段是独立存储，嵌套 struct 和数组成员递归复制，指针成员只复制指针值（仍共享被指对象），不做整体深拷贝 |
| 编译期常量 | `sizeof`/`alignof`/`offsetof` 不传播污点 |
| 数值污点 | `atoi`/`strtol`/`strlen` 等结果和以 `%d`/`%x`/`%f` 等格式化的数字文本是“数值污点”（`cNumericTaint`），算术运算保持该标记：命令/路径/SQL 等注入类 sink 忽略它，长度类（`CBufferOverflow`）和格式串类（`CFormatString`，数字可选择 `%N$` 位置参数、控制宽度）sink 仍报告 |
| 时间预算 | 每个 entrypoint 最长执行 `entryPointTimeoutQuickMs`（默认 2 分钟），超时后在函数调用边界停止，已产生的告警保留 |
| 控制流 | 每次函数调用有独立的控制流状态：`return`/`break`/`continue`/`goto` 之后路径不可达，直到执行到 goto 的目标标签（只在匹配的标签恢复，跳过中间的其它标签；可跳出嵌套块）；goto 跳转时记录变量快照，在目标标签处与顺序到达的路径合并（条件 goto 的两条路径都保留）；if 两个分支都突然完成时之后不可达，单分支 if 之后仍可达；单分支 if 以 return 结束时，分支内的写入不流到 if 之后；循环按两轮展开，`break` 结束循环、`continue` 进入下一轮、确定进入且 `return` 时循环之后不可达；`switch` 中 `break` 在 switch 处消耗；C 整数常量表达式折叠（`if (1-1)`、`while (0)`、`0 && x`、`1 \|\| x`、`c ? a : b`），短路时右侧不求值；`do-while` 至少执行一次 |
| 库函数 | `c-builtins.ts`：按函数语义写回输出参数。完整覆盖（`strcpy`、`sprintf`/`snprintf`、长度为 `sizeof dst` 或不小于数组长度的 `memcpy`/`memset`/`strncpy`）后 dst 只携带写入内容的污点（写入干净内容即清除污点）；部分写入（`strcat`、带偏移的目标、较短长度）保留原有内容；长度为常量 0 不写入；格式化函数按格式串（`%%`、`*` 宽度/精度、`%n`）对应实参，只有被消耗的实参参与写入；`sscanf` 按转换写入各输出参数。覆盖宽字符版本 |
## 4. 已知局限

| 局限 | 影响 | 说明 |
| --- | --- | --- |
| 只解析能找到的头文件 | `<x.h>` 只在 `--cIncludeDir` 中查找；系统头文件不读取，其中的宏不展开 | 用 `--cIncludeDir` 指定项目的 include 目录 |
| 不做路径敏感的值分析 | 白名单校验 + 提前 `return` 的安全写法会被报出（CASTLE 安全样本的主要误报来源） | 可通过 ruleconfig 的 sanitizer 按项目配置 |
| 两个分支的 if 中一侧 return | `if (c) { p = x; return; } else { ... }` 中 return 分支的写入仍会与另一分支合并（可能误报）；单分支的 `if (c) { ...; return; }` 已按“只有不进入分支的路径继续”处理 | Engine 两分支 if 在共享状态上合并（BVT），需要分支级状态才能丢弃 |
| 后向 goto 不重新执行 | `retry:` 形式的循环只按顺序执行一次 | 与循环两轮展开相比是不足近似 |
| 内存级精度 | 缓冲区按整体建模：部分写入只能“保留原有 + 加入新内容”，不跟踪字节区间；指针算术得到的指针不再关联原位置 | |
| 内存安全类缺陷 | 越界、UAF、double free 等不在污点分析范围 | CASTLE 中非污点 CWE 的检出率低是预期结果 |
| 深调用树的分析代价 | 大项目的主处理函数（如 curl 的 `operate`）会用满单 entrypoint 时间预算后被截断 | 需要函数摘要等优化 |
| 联合体按变量名识别 | 同一文件中不同作用域的同名变量会被一起视为 union | 实际代码中很少见 |
