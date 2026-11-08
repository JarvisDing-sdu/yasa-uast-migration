# Yasa C++ 支持：设计文档

日期：2026-11-08　状态：待确认

## 1. 背景与目的

Yasa 是静态漏洞检测引擎，目前通过污点分析支持 C，但不支持 C++：parser 只用 tree-sitter-c，Engine 只有 `CAnalyzer`，只扫描 `.c` / `.h` 文件。本项目要让 Yasa 能扫描 C++ 项目，用与 C 相同的污点分析思路发现 C++ 代码中的漏洞：外部输入（网络、环境变量、标准输入、文件）流入危险函数（命令执行、格式化输出、文件路径、内存拷贝等）。

验收方式参照 C 扩展已有的四项验收（`workstreams/yasa-c-extension/docs/C扩展-四项验收报告.md`）：功能单测、自建靶场的语义流通、大项目解析和真实漏洞测试集的命中率。

## 2. 目标、非目标与失败标准

### 目标

1. 新增独立的 `cpp` 语言：`--language cpp` 扫描 C++ 项目，输出 SARIF 漏洞报告，并支持 `--dumpAllCG` 输出调用图。
2. 第一版覆盖真实 C++ 代码和 Juliet C++ 用例中常见的特性：命名空间、类与成员函数（含类外定义）、构造与析构、继承与虚函数、引用、`new` / `delete`、`std::string`、常用容器、iostream / fstream、lambda。
3. 通过第 6 节的四项验收，并保证第 4 节的 C 回归基线完全不变。

### 非目标（第一版不做）

- 模板的语义：模板代码要能解析、不崩溃，函数体照常分析，但不做模板实例化和按模板参数区分的类型推导。
- 异常的控制流：`try` / `catch` 中的代码照常分析，但不建模 `throw` 之后的跳转。
- 运算符重载的语义：只对第 5.4 节列出的标准库运算符（如 `std::cin >>`、`std::string +`）建模，用户自定义的重载不解析到函数体。
- C++20 模块、协程、概念。
- Windows 专有的 C++ API。目标平台与 C 一致，默认 Linux。

### 失败标准（即使技术上能跑也算失败）

- 现有 C 支持的任何行为发生变化：第 4 节的任一基线出现差异。
- 针对测试集“刷分”：按文件名、函数名或 Juliet 的固定写法做特判，修改测试标签，或只挑能检出的用例统计。
- 声称支持了实际没有支持的特性。报告中必须区分“已建模”“只解析不建模”和“不支持”。

## 3. 约束

- **仓库结构**：代码分属两个组件仓库，JarvisDing-sdu/yasa-uast（parser）和 JarvisDing-sdu/yasa-engine（Engine）。集成仓库 JarvisDing-sdu/yasa-uast-migration 用子模块固定版本，并存放工作流文档、靶场和验收结果。本项目新建 `workstreams/yasa-cpp-extension/`。
- **依赖版本**：tree-sitter-cpp 选用 0.23.x（当前 0.23.4，自带 wasm；它的语法基于 tree-sitter-c ^0.23.1 扩展而来）。web-tree-sitter 与 parser-C 使用同一版本（0.26.x）。
- **提交**：作者为 sijie52 / sijie5452@gmail.com，提交说明和 PR 中不写 AI 共同作者。
- **每一步动手前先向 sijie52 报备**；涉及推送、合并、发布的操作单独确认。

## 4. 保证 C 不受影响

### 隔离方式

- C++ 走独立的语言注册：parser 注册表新增 `cpp`，启动器新增 `CppAnalyzer`，规则和 checker 包另起名字。`--language c` 的执行路径不经过任何 C++ 代码。
- `CppAnalyzer` 继承 `CAnalyzer`，只在子类中增加或覆盖行为，不修改 `CAnalyzer` 的现有逻辑。
- parser-C 只允许一处改动：增加供 parser-CPP 复用的扩展点（见 5.2）。C 调用时不传扩展参数，输出必须与改动前逐字节一致。
- 如果实现中确实需要修改 C 的共用代码（例如把 `CAnalyzer` 里写死的 `.c` / `.h` 判断提取成可覆盖的方法），只允许做不改变 C 行为的重构，并且必须单独提交、单独通过下面的回归。

### C 回归基线（改动前先记录，每个里程碑和最终验收都要复核）

| 基线 | 当前值 |
| --- | --- |
| parser-C 单测 | 69/69 |
| Engine `npm run test-c` | 111/111 |
| sast-c 靶场（164 例） | TP 110 / FN 0 / TN 54 / FP 0 |
| parser-C 对 C 语料的 UAST 输出 | 改动前后逐字节一致（语料：sast-c；curl `b052c835`、Redis `ad49ff0d`、SQLite `9626d89e`，与 C 验收报告和调用图评测使用的版本相同） |
| Juliet C（CWE-78、CWE-134，char + wchar_t，6,080 例） | 与 C 验收报告记录的结果一致 |
| curl 调用图评分（callgraph-eval） | 直接调用和回调子集的分数不变。评测输入和 gold 若本地已不存在，从 Release `c-callgraph-eval-2026-11` 的证据包恢复 |

## 5. 技术方案

### 5.1 语言接入

- CLI：`--language cpp`。C 的编译配置参数（`--cDefine`、`--cUndefine`、`--cTarget`、`--cIncludeDir`、`--cUnknownMacros`）同样适用于 C++，不另起新名字。
- 扫描的文件：`.cpp`、`.cc`、`.cxx`、`.c++`、`.hpp`、`.hh`、`.hxx`、`.h`、`.inl`。在 `cpp` 模式下 `.h` 按 C++ 解析；`.c` 文件不扫描。混合 C/C++ 的项目，C 部分仍用 `--language c` 单独扫描（见第 8 节）。
- 新增 checker 包 `taint-flow-cpp-default`，规则文件 `resource/example-rule-config/rule_config_cpp.json`。

### 5.2 Parser：新建 `uast/parser-CPP`

- 新 npm 包 `@ant-yasa/uast-parser-cpp`，加载 `tree-sitter-cpp.wasm`，对外接口与 parser-C 相同（`Parser.init()`、`Parser.parse(content, opts)`）。
- **复用 parser-C 的方式（已定）**：在 parser-C 中增加扩展点，而不是复制代码。具体为：
  - 允许指定 tree-sitter 语言（默认仍是 C）；
  - 允许传入“节点类型 → 处理函数”的扩展表，处理函数可以调用默认的访问逻辑；
  - 导出 parser-CPP 需要的辅助函数和 `MacroEnvironment`。
  C 调用时三者都不传。验收标准是：parser-C 单测全部通过，并且 C 语料的 UAST 输出逐字节一致。如果实现中发现扩展点无法做到逐字节一致，应停下来报告，不得改为放宽一致性要求。
- 预处理沿用 `MacroEnvironment`。C++ 模式下预定义 `__cplusplus`（默认 201703L），其余平台宏与 C 相同。
- C++ 节点到 UAST 的映射（第一版）：

| C++ 语法 | UAST 表示 |
| --- | --- |
| `namespace N { ... }`、`N::f`、`using namespace N` | 带命名空间限定的名字；查找时先当前命名空间，再外层，再 `using` 引入的 |
| `class` / `struct`（含成员函数、访问控制） | `ClassDefinition`，成员函数为 `FunctionDefinition`；访问控制只记在 `_meta` 中 |
| 类外定义 `void X::f() { ... }` | 归属到类 `X` 的成员函数 |
| 构造 / 析构函数、成员初始化列表 `: a(x)` | 构造函数体之前先执行初始化列表；析构函数作为普通成员函数 |
| 继承、`virtual`、`override`、纯虚函数 | `ClassDefinition` 的父类列表，`_meta` 中记录虚函数标记 |
| `new T(args)` / `delete p` | `NewExpression` / 带 `_meta` 标记的调用 |
| 引用 `T&`、`T&&`（参数、变量） | 类型中标记为引用；语义见 5.3 |
| `this` | `ThisExpression` |
| lambda | 函数表达式，捕获列表记在 `_meta` 中 |
| `static_cast` 等四种转换 | `CastExpression` |
| 模板声明、模板实参 | 解析函数体和类体，模板参数当作未知类型；`f<T>(x)` 的被调函数名为 `f` |
| `try` / `catch` / `throw` | `TryStatement`，`throw` 作为表达式语句 |
| 范围 for `for (auto &x : v)` | 与其他语言的范围循环表示一致 |
| `nullptr`、`true` / `false`、原始字符串、`auto` | 对应的字面量；`auto` 为动态类型 |
| `extern "C" { ... }` | 与 parser-C 一致，按普通声明处理 |

### 5.3 Engine：`CppAnalyzer extends CAnalyzer`

- **模块和文件**：头文件与源文件的判断按 5.1 的扩展名覆盖；头文件中的内联函数、类定义对包含它的编译单元可见，沿用 C 的处理方式。
- **类与对象**：类的实例是对象值，字段沿用 C 的结构体模型（含按值复制）。成员函数调用时绑定隐式 `this`。类外定义的成员函数在所有编译单元处理完后挂到类上。
- **虚函数**：通过基类指针或引用调用时，按对象值的实际类型查找方法，与 JS、Python 中按值分派的做法一致。值未知时，在 `--dumpAllCG` 中复用 `c-callbacks.ts` 的按类型汇总思路，连到该类及其子类的覆盖实现，并在报告中注明这是上近似。
- **引用**：引用参数按“隐式取地址”处理，复用 C 的指针写回模型，使被调函数中对引用的修改对调用方可见。
- **命名空间**：函数和全局变量按限定名登记；未限定的调用按 5.2 的顺序查找。
- **标准库模型**（在 `c-builtins.ts` 的模式上新增 C++ 模型，不修改 C 的模型）：
  - `std::string` / `std::wstring`：构造、赋值、`c_str()`、`data()`、`+` / `+=`、`append`、`substr`、`operator[]` 传递污点；
  - 容器 `std::vector` / `std::list` / `std::map` / `std::deque` / `std::set`：插入类操作把污点加入容器，读取类操作和迭代器取出容器的污点（第一版按整个容器建模，不区分元素）；
  - iostream / fstream：`std::cin >>`、`std::getline`、`istream::read` / `get` 为输入来源；`ifstream` / `ofstream` / `fstream` 的构造函数和 `open` 为路径类危险函数；
  - `new` / `delete`、`std::unique_ptr` / `std::shared_ptr` 的 `get()` 与解引用：指针语义与 C 相同。

### 5.4 规则与 checker

- `rule_config_cpp.json` 包含 C 的全部规则，再加上 C++ 的 source 和 sink。成员函数和运算符按“接收者类型 + 方法名”匹配，复用 Engine 已有的按调用者类型匹配 sink 的工具（`matchSinkAtFuncCallWithCalleeType`）。
- checker `taint_flow_cpp_input` 复用 C checker 的逻辑（继承或组合），不修改 `taint_flow_c_input`。
- 数值污点等 C 已有的语义在 C++ 中保持一致。

## 6. 验收

与 C 的四项验收一一对应，另加 C 回归。

1. **功能单测**：parser-CPP 单测覆盖 5.2 映射表的每一行；Engine 新增 `npm run test-cpp`，覆盖 5.3 的每一项。
2. **自建靶场 `sast-cpp`**：放在 `workstreams/yasa-cpp-extension/benchmark/`，格式与 sast-c 一致（`_T` 必须检出，`_F` 不得报告）。用例覆盖第 5 节的每个特性，每个特性都要有正例和反例；标签用 clang++ 编译运行核对，做法同 `c_semantics_oracle.py`。标准：全部正例检出，全部反例无误报。
3. **大项目解析**：tinyxml2（小）、leveldb（中）、aria2（大，约 18 万行）、cppcheck（超大，约 35 万行），各自按项目的构建配置运行。标准：0 崩溃；按与 C 验收相同的口径，统计 UAST 中保留的函数数占 tree-sitter 识别函数数的比例，并解释差额；记录运行时间和峰值内存。
4. **Juliet C++**：使用 C 验收时同一份 Juliet（`arichardson/juliet-test-suite-c` @ `f88433e`）中的 C++ 用例：CWE-78（2,200 个文件）、CWE-134（1,560）、CWE-23（3,900）、CWE-36（3,900）。新增 `juliet_cpp.py`：支持 `.cpp` 文件、类成员函数、81～84 号变体中整个文件属于 bad 或 good 流的情况。按 CWE 和 flow 变体分别报告 TPR、FPR。不设硬性数字（sijie52 的决定）：目标是在没有特判的前提下尽量接近 C 的水平，达不到的部分按 CWE 和变体如实报告原因。
5. **C 回归**：第 4 节的全部基线不变。

## 7. 里程碑

| 里程碑 | 内容 | 完成标志 |
| --- | --- | --- |
| M0 | 记录 C 回归基线 | 第 4 节表格中各项的当前值和 UAST 输出存档 |
| M1 | parser-C 扩展点、parser-CPP 骨架、`cpp` 语言接入，先支持 C++ 中的 C 子集和命名空间 | Juliet C++ 01 号变体能跑通；C 回归不变 |
| M2 | 类、成员函数、构造与析构、继承与虚函数、引用 | Juliet 81～84、33 / 43 / 62 号变体；对应的 sast-cpp 用例 |
| M3 | 标准库模型和 C++ 规则 | Juliet 72～74 号变体、路径穿越两类；对应的 sast-cpp 用例 |
| M4 | 四项验收和报告 | `workstreams/yasa-cpp-extension/docs/` 下的验收报告 |

每个里程碑结束时复核 C 回归，并向 sijie52 汇报。

## 8. 风险

- tree-sitter-cpp 在模板密集或宏密集的代码上可能出现解析错误。处理方式与 C 一致：记录 `parseErrors`，保留能恢复的语句。cppcheck 用于暴露这类问题。
- 混合 C / C++ 的项目：`.c` 文件在 `cpp` 模式下不扫描，`.h` 按 C++ 解析。同一项目需要扫描两次。第一版不做混合语言的统一分析。
- 虚函数和容器都是上近似，可能带来误报；靶场需要有对应的反例，验收报告要单独说明。
- 大项目的性能：在 aria2、cppcheck 上记录时间和内存。超出 C 验收时 curl 的量级时，先报告，不擅自放宽超时或关闭功能。

## 9. 留给实现者决定的

- 扩展点的具体函数签名，以及 parser-CPP 内部的代码组织；
- UAST 中命名空间限定名的具体编码方式（例如 `N::f` 还是嵌套作用域），只要查找规则满足 5.2；
- 标准库模型的实现顺序，以及每个模型的具体写法；
- sast-cpp 用例的具体数量和目录划分，只要覆盖第 5 节每个特性且有正反例；
- `juliet_cpp.py` 与 `juliet_c.py` 是共用代码还是分开写。
