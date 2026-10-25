# sast-c：C 语言语义流通靶场

xAST（`alipay/ant-application-security-testing-benchmark`）没有 C 版本，这里按 xAST 的格式写了一套 C 靶场，用来验证 C 的各种语法能否让污点从 source 流到 sink（验收第 2 项）。

## 约定

- 文件名或目录名以 `_T` 结尾：必须检出；以 `_F` 结尾：不能检出。
- 每个用例的头部注释记录评价项和场景，格式与 xAST 一致。
- source 统一为 `taint_src()` 的返回值，sink 统一为 `taint_sink()` 的参数；`real_api/` 下的用例改用真实的 `getenv`/`fgets`/`recv`/`scanf`/`read`、`system`/`printf`/`popen`/`strcpy`/`fopen`/`sqlite3_exec`。
- 多文件用例是一个以 `_T`/`_F` 结尾的目录（例如跨文件调用、`extern` 全局变量、头文件内联函数）。
- 规则：`rule_config_xast_c.json` = 默认 C 规则 + `taint_src`/`taint_sink`。

## 覆盖范围（82 个用例：65 T / 17 F）

| 目录 | 内容 |
| --- | --- |
| `completeness/expression` | 赋值、连续赋值、三目、类型转换、逗号、指针运算、常量、覆盖赋值、sizeof |
| `completeness/pointer` | 取地址、指针复制、通过指针写回、输出参数、两个指针指向同一变量 |
| `completeness/preprocessor` | `#ifdef`、`#if/#else`、头文件保护、宏替换 source、`#ifdef` 中的 case |
| `completeness/cross_file` | 跨文件调用、跨文件返回值、头文件 static inline、extern 全局变量 |
| `completeness/libc_propagation` | strcpy、strcat、sprintf、snprintf、memcpy、strncpy、sscanf、strdup，以及常量拷贝等反例 |
| `accuracy/field_sensitive/array` | 下标区分、初始化列表、二维数组 |
| `accuracy/field_sensitive/struct` | `.`/`->`、字段区分、别名、指定初始化器、嵌套、typedef、结构体指针参数、union |
| `accuracy/context_sensitive` | 参数/返回值传递、多次调用区分上下文、函数指针、回调、递归、全局变量 |
| `accuracy/flow_sensitive` | if/else、while、for、do-while、switch、goto、循环携带依赖、死分支、return 后代码、`while(1){...break;}` |
| `real_api` | 真实 API 的命令注入、格式化字符串、缓冲区溢出、路径穿越、SQL 注入及安全写法 |

## 运行

```bash
cd engine
npx tsx src/main.ts \
  --sourcePath ../workstreams/yasa-c-extension/benchmark/sast-c/case \
  --language c \
  --ruleConfigFile ../workstreams/yasa-c-extension/benchmark/rule_config_xast_c.json \
  --checkerPackIds taint-flow-c-default \
  --report /tmp/sast-c-report
python3 ../workstreams/yasa-c-extension/scripts/score_c_benchmark.py \
  /tmp/sast-c-report/report.sarif ../workstreams/yasa-c-extension/benchmark/sast-c/case
```

注意：这套靶场和 C 实现由同一人编写，结果只能说明实现覆盖了这些设计好的场景，不能代替独立靶场。独立评估见 Juliet 与 CASTLE 的结果。
