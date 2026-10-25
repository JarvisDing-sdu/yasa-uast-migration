# C 语言扩展：设计与实现

本文说明 YASA 的 C 语言支持是怎么实现的，以及相对于之前那版 C 原型（`sijie52/parser-c`）改了什么、为什么改。验收数据见 [四项验收报告](C扩展-四项验收报告.md)。

## 1. 整体链路

```text
.c/.h 源码
  │  uast/parser-C：tree-sitter-c (WASM) → CST → visitor → UAST
  │      宏展开、#if 全分支保留、ERROR 区域恢复
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

- **宏展开**：收集本文件的 `#define`，在使用处展开对象宏和函数宏，支持 `#x`、`a ## b`、`__VA_ARGS__`；同一个宏有多份定义时优先选非 Windows 分支（`#ifdef _WIN32 ... #else ... #endif`）。展开文本重新解析成语句或表达式，所有节点的位置改写为宏使用处，并防止递归展开。真实 C 代码与 Juliet 大量通过宏调用 sink（`EXECL(...)`），不展开就几乎检不出。
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
| 链接 | 非 `static` 的函数和文件级变量放进 topScope，所有文件共享；`extern` 声明不再创建同名局部变量；头文件中的 `static inline` 函数同样全局可见 |
| `#include` | 不做模块导入（函数已全局可见） |
| 指针 | `&x` 记录被指向的变量；`*p = v` 写回该变量；`*p` 读取该变量的当前值。覆盖输出参数、两个指针指向同一变量等情况 |
| 聚合类型 | 未初始化的结构体/数组局部变量初始化为空对象；多级写入 `g[1][0] = x` 前先建出中间层 |
| 编译期常量 | `sizeof`/`alignof`/`offsetof` 不传播污点 |
| 数值转换 | `atoi`/`strtol` 等返回值不携带注入类污点 |
| 时间预算 | 每个 entrypoint 最长执行 `entryPointTimeoutQuickMs`（默认 2 分钟），超时后在函数调用边界停止，已产生的告警保留 |
| 控制流 | `do-while` 至少执行一次；循环体以无条件 `break`/`return` 结尾时只执行一次；`return`/`break`/`continue`/`goto` 之后到下一个标签前的语句视为不可达；`if (0)`/`if (1)` 只执行可达分支；处理标签语句 |
| 库函数 | `c-builtins.ts`：`strcpy`/`strcat`/`memcpy`/`sprintf`/`snprintf`/`sscanf`/`realpath` 及其宽字符版本（`wcscpy`/`wcsncat`/`wmemcpy`/`swprintf` 等）把污点写回输出缓冲区（包括 `buf + n`、`&buf[i]` 形式的实参） |

### 3.3 taint_flow_c_input（`src/checker/taint/c/c-default-taint-checker.ts`）

- **entrypoint**：调用图中没有调用者的函数（包括 `main`），按“main 优先、文件+行号”排序以保证结果可复现；ruleconfig 中声明的 entrypoint 也会加入。
- **source**：`main` 的 `argv`/`envp`；ruleconfig 中的 `FuncCallReturnValueTaintSource`（`getenv` 等）和 `FuncCallArgTaintSource`（`fgets`/`recv`/`read` 等）。写入型 source 的实参是 `(char *)(data + len)` 这类表达式时，污点同时标到被写入的变量上。调用图根函数的参数**不**标为 source，否则库代码中每个对外函数都会被当成攻击面。
- **sink**：ruleconfig 中的 `FuncCallTaintSink`，按函数名匹配。

### 3.4 默认规则（`rule_config_c.json`）

| 类别 | sink |
| --- | --- |
| 命令注入 | `system`、`popen`、`exec*`、`dlopen`，以及 Windows CRT 的 `_system`、`_popen`、`_exec*`、`_spawn*`、`_w*` |
| 格式化字符串 | `printf`/`wprintf` 系列的格式串参数（含 `_snprintf`、`_snwprintf` 等 Windows 变体）、`syslog` |
| 缓冲区溢出 | `strcpy`/`strcat`/`wcscpy`/`wcscat` 的源参数，`memcpy`/`memmove` 的长度参数 |
| 路径穿越 | `fopen`、`open`、`openat`、`unlink`、`rename`、`chmod`、`mkdir` 等 |
| SQL 注入 | `sqlite3_exec`/`sqlite3_prepare*`、`mysql_query`、`mysql_real_query`、`PQexec` |

注意：Engine 的 `args` 只认单个下标或 `"*"`。码医生规则里的 `"0:"`、`"1:"` 写法会被解析成只有第 0、1 个参数，导致 `execl(path, ..., data, NULL)` 的命令参数从未被检查；新规则对可变参数 sink 使用 `"*"`，对 `scanf` 类 source 列出具体下标。`strncpy`/`strncat` 的长度参数不作为 sink：它通常由 `strlen` 计算，是限制拷贝长度的保护写法，作为 sink 只会产生误报。

## 4. 已知局限

| 局限 | 影响 | 说明 |
| --- | --- | --- |
| 宏只在本文件内展开 | 头文件里定义的宏不展开 | 需要 include 解析和宏表跨文件传递 |
| 不做路径敏感的值分析 | 白名单校验 + 提前 `return` 的安全写法会被报出（CASTLE 安全样本的主要误报来源） | 可通过 ruleconfig 的 sanitizer 按项目配置 |
| `if/else` 两个分支按顺序执行在同一状态上 | 少数“两个分支都写同一变量”的场景会过度近似 | Engine 基类行为 |
| 数值转换是注入类污点的屏障 | `memcpy(dst, src, atoi(input))` 这类整数长度不再被追踪 | 与 CodeQL 注入类查询的处理一致 |
| 内存安全类缺陷 | 越界、UAF、double free 等不在污点分析范围 | CASTLE 中非污点 CWE 的检出率低是预期结果 |
| 深调用树的分析代价 | 大项目的主处理函数（如 curl 的 `operate`）会用满单 entrypoint 时间预算后被截断 | 需要函数摘要等优化 |
| 联合体按变量名识别 | 同一文件中不同作用域的同名变量会被一起视为 union | 实际代码中很少见 |
