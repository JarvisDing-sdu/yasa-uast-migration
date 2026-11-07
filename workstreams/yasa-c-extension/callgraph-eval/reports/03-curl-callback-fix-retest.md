# Yasa C 回调修复：curl 复测结果（未提交候选）

- 时间：2026-11-07
- Engine：`work/callback-fix/engine`，基于 `e2f89d9`（分支 `fix/c-callback-resolution`，未提交）。C parser 仍是 `curl-large/fix-candidate/parser-C`（与 yasa-fixed 相同）。
- 输入、配置、node、8 GB 堆与 `curl-large/results/yasa-fixed` 完全相同；评分复用 `curl-large/score.py`、`export_predictions.py`，gold 与冻结回调子集未改动。
- 原始结果：`results/yasa-callback/`（run.json、report/、normalized.json、score.json、mismatches.json）。

## 修改内容

| # | 问题 | 修改 |
| --- | --- | --- |
| 1 | 非 static 全局变量的初始化器在 topScope 求值，找不到本文件的 static 函数（`Curl_DIGEST_MD5 = { my_md5_init, … }`） | 初始化器在本编译单元 scope 求值，变量仍存于 topScope |
| 2 | 头文件中定义的 struct 的按位置初始化列表未按字段名键化 | `CTypeIndex.keyInitializer`：按字段顺序键化，递归处理数组与嵌套 struct |
| — | 原有缺陷：同一行的嵌套初始化列表 sid 相同，struct 按值复制时内层成员丢失（修 2 时暴露） | 成员副本放在外层副本之下 |
| 3 | `--dumpAllCG` 逐函数分析，`p->cb(...)` 的 p 来自参数或回调由其他函数写入 | 新增 `c-callbacks.ts`：按“struct 名.字段名”汇总写入该字段的函数（赋值、宏展开出的赋值、初始化列表）；仅在 `--dumpAllCG` 中为调用处补调用边，不执行候选函数，污点分析不受影响 |

## 测试

| 项 | 修改前 | 修改后 |
| --- | --- | --- |
| `test/c/test-c-callgraph.ts`（新增 21 项，含类型隔离反例） | 3/21 | 21/21 |
| 新增嵌套复制语义用例（2 T + 1 F，clang 核对标签） | — | 3/3 |
| `npm run test-c` 全部 | 87/87 | 111/111 |
| Engine `tsc --noEmit` | — | 0 错误 |
| sast-c 164 例 | TP 110 FN 0 TN 54 FP 0 | 完全相同 |

## curl 结果（与 yasa-fixed 同输入）

| 指标 | yasa-fixed | 回调修复版 |
| --- | ---: | ---: |
| 无宏直接调用 callsite-target：TP / FP / FN | 7453 / 0 / 57 | 7453 / 0 / 57 |
| 无宏直接调用函数对：精确率 / 召回率 | 100% / 99.43% | 100% / 99.43% |
| 完整 AST 直接调用对召回率 | 6877/6959 = 98.82% | 6877/6959 = 98.82% |
| 精选真实间接调用子集（11 点 / 25 边） | 0/25 | **25/25** |
| 运行时间 | 151.5 s | 160.6 s（未控制并发，不作速度比较） |

- 直接调用的评分完全不变；与 yasa-fixed 相比没有任何已解析记录消失。
- 11 个调用点上 gold 之外的目标：hmac-init/update/final 各多 1 条，均为 `lib/curl_sha512_256.c` 的 SHA512/256 函数。gold 明确把“未作为实参使用的 SHA512/256 HMAC 对象”排除，这是按类型汇总的已知上近似。其余 8 个点没有多余目标。
- 全项目新增已解析记录 1,199 条（1,064 个调用方-目标函数对，196 个调用行）。这些边不在本评分口径的总体内。审计见 [audit/AUDIT.md](audit/AUDIT.md)：clang 独立核对全部类型可行（1,199/1,199）；20 行人工抽样的调用点精确率 59.5%–66.9%（121 对：正确 72、错误 40、不确定 9）。
- 25 条样本的结果不能外推为全项目回调召回率。
