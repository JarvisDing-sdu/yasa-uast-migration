# b 项阶段一：旧新 UAST 双侧 emitter 验证（PyTorch Phase 1）

## 目的

本记录验证同一份 Python 源码经旧 external `uast4py` binary 和新 Node.js Tree-sitter
parser 后，是否都能被**同一个** `PythonEmitter` 公平消费。

这里的 emitter round-trip 指：

```text
UAST A → PythonEmitter → source.py → Python parser → UAST B
```

比较的是生成前后的 UAST 语义，而不是要求原始源码与生成源码字节相同。首要 parser
判据始终是 `canonical(UAST_old)` 与 `canonical(UAST_new)` 的直接比较；round-trip 是
第二层证据，用于发现 emitter 或 UAST 自身的信息损失。

PythonEmitter 的严格输入只有 UAST JSON，不读取原始 `source.py`、PyTorch `expected.json`
或另一侧 parser 的输出。未知节点 fail-closed，避免静默生成错误源码。

```text
source.py
  ├─ old uast4py binary → uast.old.json → PythonEmitter → source.old.py
  └─ new Tree-sitter    → uast.new.json → PythonEmitter → source.new.py
```

emitter 只读取各自的 UAST JSON，不读取原始 `source.py`、`expected.json` 或另一侧输出。

## 输入与工具

输入是 DL 研究工作流中的 20 个确定性 PyTorch Phase 1 样例：

```text
workstreams/dl-cross-language-research/fixtures/generated/dl-uast-seed/DL001...DL020
```

它们覆盖 Tensor 创建、shape 操作、切片、基本算术、矩阵乘、归约与激活函数。该语料是
b 项的小型可执行阶段，不等同于后续“大项目全量还原”。

新增工具：

| 文件 | 用途 |
| --- | --- |
| `workstreams/yasa-python-migration/scripts/parse_new_python_uast.js` | 调用已构建的新 npm parser，将单个 Python 文件的内存 `CompileUnit` 写成测试用 JSON。生产 Engine 不需要这个落盘步骤。 |
| `workstreams/dl-cross-language-research/scripts/build_old_new_emitter_phase1.py` | 对每个 case 生成 old/new UAST、old/new emitter 源码、fidelity report 和汇总报告。 |
| `uast/emitter-Python/src/cli.js` | 同一个确定性 PythonEmitter CLI。 |

所有 case 产物写在 Git 忽略的生成目录中：

```text
uast.old.json
uast.new.json
source.old.py
source.new.py
emitter.old.report.json
emitter.new.report.json
phase1-old-new-emitter-summary.json
```

## 复现命令

先构建新 npm parser：

```bash
cd uast/parser-Python
npm run build

cd ../..
python3 workstreams/dl-cross-language-research/scripts/build_old_new_emitter_phase1.py \
  --old-binary runtime/uast-v0.2.18/uast4py-linux-amd64
```

## 2026-09-13 结果

| 项目 | 结果 |
| --- | ---: |
| 输入 case | 20 |
| old binary 成功解析 | 20 / 20 |
| new Tree-sitter 成功解析 | 20 / 20 |
| old UAST 成功经 emitter 生成 | 20 / 20 |
| new UAST 成功经 emitter 生成 | 20 / 20 |
| old/new emitter 输出源码字节一致 | 20 / 20 |
| `source.old.py` 运行结果匹配原始 PyTorch oracle | 20 / 20 |
| `source.new.py` 运行结果匹配原始 PyTorch oracle | 20 / 20 |
| old emitter 输出经新 parser 语义 round-trip | 20 / 20 |
| new emitter 输出经新 parser 语义 round-trip | 20 / 20 |
| 严格 canonical UAST 一致 | 4 / 20 |
| float 语义归一化后 canonical UAST 一致 | 20 / 20 |

严格 JSON 比较中的 16 个差异均为同一种 wire-format 差异：

```json
// old external binary
{ "type": "Literal", "value": 1.0, "literalType": "float" }

// new Node.js parser JSON
{ "type": "Literal", "value": 1, "literalType": "float" }
```

两侧都保留 `literalType: "float"`；JavaScript 的单一 `Number` 类型在
`JSON.stringify()` 时不能保留 `1.0` 的书写形式，因此写为 `1`。比较器保留严格结果，
并额外按 `literalType=float` 把两侧数值规范化为语义 float。规范化后 20/20 一致，且
emitter 两侧都稳定输出 `1.0`，所以 `source.old.py` 与 `source.new.py` 20/20 相同。

本次计时（包含每个 case 单独启动进程）：

| 阶段 | 总耗时 |
| --- | ---: |
| old binary parse | 7.70 s |
| new parser JSON export | 1.85 s |
| old UAST emitter | 0.38 s |
| new UAST emitter | 0.39 s |

运行与重新解析由：

```text
workstreams/dl-cross-language-research/scripts/verify_old_new_emitter_phase1.py
```

完成。两侧源码都在固定 CPU、固定随机种子、`1e-6` 浮点容差下与原始 `expected.json`
一致；两侧重新交给新 parser 后也都与各自输入 UAST 语义一致。

## 后续事项

1. 已在 PyTorch 上游 122 个真实 Python 文件上继续阶段二，见
   [阶段二报告](PyTorch真实源码-解析与还原.md)；
2. 对严格 float JSON 表示差异决定最终 UAST canonical 规则，并在 a 项验收中明确记录；
3. 分类真实 PyTorch 语料中的 old/new UAST 差异与不可逆推导式/生成器降级结构。
