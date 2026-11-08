# C++ M1 评审修复结果

状态：本轮修复与验证完成，已写回本地分支。尚未推送，等待独立复审。

## 范围与仓库

本次处理 `C++-M1-评审结果.md` 和 `Codex-交接说明-C++支持.md` 中的 M1 问题，没有开始 M2/M3，没有推送远程。

三个仓库继续使用 `feat/cpp-support-m1`。先在本地副本合入已有 main，再修复：

- 集成仓库 main：`57ff0a256189d38a5924c104b03777b2eaa6f9c4`。
- Engine main：`555f6e15bb420085cc8147950577e3cdf46a3827`，含 `7da199b` 的编译单元控制流重置。
- UAST main：`81534004fe9a1f705369de223a2e1046d7cbb362`。
- 集成修复提交：`6aa25a1209bd363d78e931b9ffa42c67e12e869e`（结果记录另作本地提交）。
- 本次 Engine 修复：`d6773455b9eea2c5ae27d54f18d003359470b38d`。
- 本次 UAST 修复：`73bb51077958db26600a578b4527d1d5ff7d0f70`。

本次修复提交只改 C++ 分析器、C++ checker、parser-CPP 和相关测试；没有额外修改 parser-C 或 CAnalyzer 的共用实现。上游的 C 修复保留。

## 逐项处理

1. **C1：名称解析。** 标识符保留使用处的命名空间及是否带前导 `::`。绝对限定从全局查找，相对限定从使用处向外查找；普通标识符先查局部，再查当前及外层命名空间。未找到的用户限定名保持限定形式，不再随意退回同名裸函数。
2. **C2：命名空间外定义。** 在访问 `void N::bad()` 的函数体前，将 N 传入解析上下文；函数体中的未限定调用能够找到 N 中的定义。
3. **C3：using 作用域。** 记录 using 的声明位置、函数/块范围和命名空间上下文，防止泄漏到别的函数或兄弟块。内层 using-declaration 可遮蔽外层局部变量；using-directive 按共同命名空间祖先参与查找，避免抢走当前命名空间已有的函数。
4. **C4：命名空间变量。** 读和写共用 `{scope, name}` 绑定。限定访问、非限定访问和 extern 声明访问同一份存储，不再复制一个容易失效的值作为别名。补充限定写/非限定读、反向读写、跨文件 extern 和安全覆盖测试。
5. **C5：匿名命名空间。** 即使位于全局匿名命名空间，也先转换为模块内部链接，再走继承的 C 路径，防止跨编译单元连接同名符号。
6. **C6：用户函数与标准库。** C++ checker 在 source/sink 前后触发点排除用户命名空间函数；分析器在进入继承的 C 库模型前保留用户函数的限定名。除 system/getenv 外，补查发现的自定义 atoi 误套数值转换模型也已修正。真实的全局/标准库调用继续使用原规则。
7. **C7：条件定义。** 命名空间函数的条件编译分支合并为候选函数并集，保留安全分支和危险分支，不依赖其先后顺序。
8. **C8：while 条件声明。** 声明位于循环 test 的 Sequence 中，每次检查重新执行；同时修正 tree-sitter-cpp 条件声明的初始化器位于 value 字段、之前未被带入 UAST 的问题。if/switch 仍只执行一次声明。
9. **I1：评测脚本。** C++ 外层先校验运行清单、选中用例、批次退出码、源文件哈希、扫描摘要和文件数量；SARIF 数量必须与摘要一致，unmapped 必须为 0，才发布评分。失败/中断/缺报告/残留批次不再被当作 FN/TN。成功且零发现的扫描可以没有 SARIF。输出目录要求为空，归档搬移后仍可按清单重新计分。没有改 C 评分脚本或 bad/good 标签。
10. **I2：混合项目。** 必经的 input 实现放入 api.h；测试断言头文件实际出现在 cpp AST 集合中、没有 parseErrors，helper.c 不参与。
11. **原始字符串。** raw_string_literal 转成字符串字面量，保留反斜杠和自定义分隔符内的原始内容，覆盖空字符串。

## 测试证据

- parser-CPP：18 项通过（原 14 项，加 4 项解析层回归）；构建通过。
- Engine C++：40 项通过（原 9 项，加 31 个独立程序反例/对照）；TypeScript 检查通过。
- C++ 反例的全部 .cpp 文件通过 `clang++ -std=c++17 -fsyntax-only`。
- C++ 计分完整性测试：13 项通过；`juliet_cpp.py --self-test` 通过，构造的两用例计分为 TP2/FN0/TN1/FP1。
- 两个修改的 Engine 实现文件 ESLint：0 errors、6 warnings。警告为 3 个 CommonJS 导入/导出风格和 3 个认知复杂度提示。没有声称全仓 lint 无警告。

先用原实现运行新增测试观察失败，再修复后运行。计分器的旧实现对 11 类不完整/异常证据仍发布结果；归档搬移测试也先在严格旧路径校验下失败，再修正。红/绿日志会一并保留。

原有 namespaces_do_not_merge_T/F 作为一个项目扫描时重复定义同一外部限定名。本次仅把这两组的命名空间改成彼此唯一的名称，未修改流程和 T/F 标签。新增反例每个目录作为独立程序扫描，避免相互覆盖。C++ 测试输出改用新临时目录，避免覆盖上一次结果。

## 完整 C 回归

完整脚本与冻结基线比较通过（exit 0）：

- parser-C 72、Engine C 112 全部通过，原基线中的测试均保留。
- sast-c：TP110 / FN0 / TN54 / FP0，逐用例一致。
- UAST：2,451 文件哈希逐项一致。
- Juliet C 四组共 6,080 用例、16 个批次：全部 exit 0，逐批次检查扫描文件数、摘要和 SARIF 数量一致；四份完整评分 JSON 与基线一致。CWE78 两种字符类型各 TP1900/FN0/TN1900/FP0；CWE134 各 TP1140/FN0/TN1140/FP0。
- curl：严格 callsite TP7453 / FP0 / FN57，full_ast found6877，人工回调集 25/25；primary_strict、full_ast_direct_pair_recall、curated_indirect 三个结果对象与基线完全相同。

这里的“与基线一致”按原比较脚本口径：原测试全保留且无失败，非测试输出逐项一致；新增测试不要求删除到原来的 69/111 项。新 summary 保存在 results/m1-review-fixes/c-regression，旧基线和旧 M1 的 10 份结果文件 SHA256 均未变。

## Juliet C++ 重测

最终 Engine/UAST 提交版本共跑 8 个集合、10 个批次：全部 exit 0，通过当前严格计分器的运行清单/报告完整性校验，unmapped 均为 0。与原始 M1 的 8 份评分 JSON 完全相同，包括逐用例和各维度结果：

- CWE78 char / wchar_t：各 500 用例，TP80 / FN420 / TN500 / FP0。
- CWE134 char / wchar_t：各 300 用例，TP48 / FN252 / TN300 / FP0。
- CWE23 char / wchar_t（01）：各 25 用例，TP10 / FN15 / TN25 / FP0。
- CWE36 char / wchar_t（01）：各 25 用例，TP10 / FN15 / TN25 / FP0。

修复反例通过，但这个 Juliet 选集的检出率没有上升；不能把本次语言语义修复写成总体召回率提升。原始 `results/m1` 继续保留，新分数另存 `results/m1-review-fixes/juliet`。

## 限制与复审重点

这轮修复处理的是 M1 的语言语义错误，不等同于完成全部 C++ 支持。类/虚函数、引用别名、STL、文件流等仍按 M2/M3 计划处理；头文件中的 using 仍未传播到包含者。本次没有验证重载、ADL、模板和命名空间别名的完整查找语义。

额外探测发现：`namespace A { char *p = getenv("X"); } void bad() { system(A::p); }` 的动态全局初始化 source 当前未检出，作为剩余限制记录，未把它算作已修复。该探测原始源码与摘要也保留。不能据本轮测试声称任意 C++ 全局初始化已支持。

建议复审重点：限定名读写是否确实落到同一存储；using 声明与指令的不同查找位置；候选函数并集的安全/危险顺序；while 后续迭代的初始化器执行；自定义标准库同名函数的返回污点是否保留。仍需独立复审后再决定合并。

## 复现入口

```bash
(cd uast/parser-C && npm run build && npm test)
(cd uast/parser-CPP && npm run build && npm test)
(cd engine && npm run test-cpp && npm run test-c && npx tsc --noEmit -p .)
python3 -m unittest discover -s workstreams/yasa-cpp-extension/scripts/tests
python3 workstreams/yasa-cpp-extension/scripts/juliet_cpp.py --self-test
bash workstreams/yasa-cpp-extension/scripts/c_regression.sh NEW_OUTPUT --compare workstreams/yasa-cpp-extension/results/c-baseline
```

完整回归的 YASA_ROOT/CORPUS/JULIET/CURL_LARGE/NODE_BUNDLE 必须指向本地已有代码和冻结语料。Juliet C++ 的选集仍为 CWE78/134 全部 C++ 变体，CWE23/36 的 01 变体，均跑 char 与 wchar_t。使用新的原始输出目录，不覆盖旧结果。


## 交付与保留

代码已同步到用户实际工作仓库，重建 parser-C/parser-CPP 后，再次运行 parser-CPP 18、Engine C++ 40、Engine C 112、tsc 和计分器 13 项检查/自测，全部通过。三个仓库在最终核对时均为干净状态。

原评审报告、原基线、原 M1 结果均保留。新结果记录在 `workstreams/yasa-cpp-extension/results/m1-review-fixes/`；原始扫描输入、run.json、扫描摘要、SARIF、引擎日志及红/绿测试日志位于 `outputs/C++-M1-修复验证-2026-11-08/`。C++ 归档后重新计分与保存结果相同。

验证文件列表及哈希见原始证据目录的 SHA256SUMS.json；源码版本和汇总见 results/m1-review-fixes/verification.json。没有推送、没有合并到 main，没有开始 M2/M3。
