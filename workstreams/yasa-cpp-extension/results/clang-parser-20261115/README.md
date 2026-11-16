# C/C++ Parser 实验结果

更新于 2026 年 11 月 16 日。可读说明见[阶段报告](../../../C与CPP解析器调研与实施规划.md)。

## 对应源码（历史首轮）

- Engine 提交为 [`0e79be4`](https://github.com/JarvisDing-sdu/yasa-engine/commit/0e79be49652ded000dc124384ca5b672b39f9af4)。
- UAST 提交为 [`2242701`](https://github.com/JarvisDing-sdu/yasa-uast/commit/2242701664c04ee7a8013a23d0e2450e5286852c)。
- 两个源码仓库使用 `codex/c-family-pilot-20261115` 分支。

## 结果材料

| 文件 | 内容 |
| --- | --- |
| [semantic-round-20261116.json](semantic-round-20261116.json) | 最新完整验收：358 项回归、六项目 523 单元；恢复参数包调用，源码提交 341fbd1 |
| [semantic-gaps-20261116.json](semantic-gaps-20261116.json) | 最新语义修复：闭包快照、枚举、继承、别名和分支；357 项回归；六项目正式 dump 复测中断，已完成范围见记录。修复尚未提交，文件内记录源码哈希 |
| [project-stability-20261116.json](project-stability-20261116.json) | 上一轮 523 单元基线：带标签分支与 typedef 数组修复 |
| [summary.json](summary.json) | 导出、定义覆盖、测试与 Engine 执行状态汇总 |
| [curl-manifest.json](curl-manifest.json) | 196 个 libcurl_static 编译单元的导出状态与转换诊断 |
| [spdlog-manifest.json](spdlog-manifest.json) | 7 个 spdlog 编译单元的导出状态与转换诊断 |
| [benchmark-verified-summary.json](benchmark-verified-summary.json) | 当前三次测量的耗时和峰值 RSS 中位数 |
| [benchmark-verified-results.json](benchmark-verified-results.json) | 每轮完整命令及原始测量值 |
| [benchmark-before-summary.json](benchmark-before-summary.json) | 优化前的阶段性能数据 |
| [reader-equivalence.json](reader-equivalence.json) | 同一真实输入下两种读取方式的 metadata/UAST 校验 |
| [definition-mismatch-audit-final.json](definition-mismatch-audit-final.json) | 13 条定义匹配差异的逐条判定 |
| [mixed-native-score.json](mixed-native-score.json) | 冻结混合语言样例的评分 |
| [spdlog-engine-manifest.json](spdlog-engine-manifest.json) | 完整 Engine 分析的失败状态 |

实验使用本机 Linux、Clang 21.1.8 和对应构建目标的编译数据库。manifest 中的源码、数据库及输出路径记录当时的本机位置。复现时重新生成本机构建配置，并选用新的输出目录。

完整 UAST JSON、源码快照、测试日志和中间归档保存在本机 `artifacts/clang-hardening-20261115/`。本目录上传结果摘要和 manifest，原始文件的校验及逐条状态保留在相应记录中。
