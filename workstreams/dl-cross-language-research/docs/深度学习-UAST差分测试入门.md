# 从 UAST 生成多语言深度学习代码：输入、测试意义与 Bug 发掘入门

> 本文回答：要输入大模型的到底是什么？PyTorch、DJL、GoMLX 等仓库用来做什么？为什么把同一功能生成到不同语言后运行，有机会发现深度学习库 bug？

## 1. 先给结论

我们通常**不把整个 PyTorch、DJL 或 GoMLX 仓库一次性输入大模型，也不把整个框架源码翻译成另一种语言**。

真正处理的对象是小型、可执行、功能明确的“深度学习测试程序”，例如：

```text
创建两个固定 Tensor
执行矩阵乘法
经过 ReLU
计算求和结果
输出 shape、dtype 和数值
```

这些程序可以来自：

- 深度学习框架官方 examples；
- 框架自身的算子单元测试；
- 已知 bug 的最小复现程序；
- 我们按照统一测试规范生成的小程序；
- 从真实模型中裁剪出的单个算子或子图。

大模型的主要输入应是：

```text
规范化 UAST
+ 深度学习语义说明
+ 目标语言
+ 目标深度学习库
+ 生成约束
```

大模型输出的是目标语言的用户级测试代码，不是目标框架的底层实现。

## 2. 一个直观例子

假设我们要测试“矩阵乘法后经过 ReLU”这个功能。

测试意图是：

```text
输入：两个固定形状、固定数值的矩阵 A 和 B
操作：C = ReLU(A × B)
输出：C 的数值、shape 和 dtype
```

首先有一个 Python/PyTorch 版本：

```text
Python 程序
  → 创建 Tensor A、B
  → 调用 PyTorch 矩阵乘法
  → 调用 PyTorch ReLU
  → 输出结果
```

YASA 将它解析为 UAST：

```text
变量声明 A、B
函数调用 matmul
函数调用 relu
变量赋值 C
输出 C
```

然后根据同一份 UAST 和深度学习语义，生成：

```text
Java + DJL 版本
Go + GoMLX 版本
TypeScript + WebDNN 版本
```

这几个程序使用不同语言、不同框架 API，但都应该表达：

```text
C = ReLU(A × B)
```

给它们相同的 A、B 后，比较结果。如果 PyTorch、DJL、ONNX Runtime 一致，而 GoMLX 稳定产生明显不同结果，就继续调查 GoMLX 路径。

## 3. 大模型到底输入什么

这里容易混淆“训练模型时的数据”和“真正使用模型时的输入”。

### 3.1 训练阶段

训练时需要构造大量输入/输出对：

```text
输入：某语言程序对应的规范化 UAST + 目标语言/库标签
输出：目标语言的正确源码
```

例如：

```text
输入：Python 程序的 UAST + <TARGET_JAVA><LIB_DJL>
输出：功能等价的 Java/DJL 程序
```

训练数据可以从框架仓库的 examples、tests 和文档样例中提取。这时我们当然会读取仓库源码，因为需要从中获得：

```text
正确 API 用法
算子签名
默认参数
输入输出类型
官方测试输入
官方期望结果
已知 bug 的回归样例
```

但不会把几百万行仓库源码原封不动拼进一次模型上下文。

### 3.2 生成/推理阶段

模型实际生成目标代码时，推荐输入：

```text
1. Canonical UAST
2. Target Language，例如 Java
3. Target Library，例如 DJL
4. DL Semantic Profile
5. 允许使用的 API 与版本
6. 输出必须可编译、可执行等约束
```

概念输入可以是：

```json
{
  "targetLanguage": "java",
  "targetLibrary": "djl",
  "libraryVersion": "fixed-version",
  "uast": { "type": "CompileUnit", "body": [] },
  "dlSemantics": {
    "operation": "Relu(MatMul(A, B))",
    "inputs": [
      { "name": "A", "shape": [2, 3], "dtype": "float32" },
      { "name": "B", "shape": [3, 2], "dtype": "float32" }
    ]
  },
  "constraints": {
    "device": "cpu",
    "deterministic": true,
    "printOutputs": true
  }
}
```

模型输出 Java/DJL 源码，然后进入编译和运行验证。

## 4. 原始源码要不要一起输入

要分任务。

### 4.1 测试 UAST 是否丢信息：不能输入原源码

当前工程要求是比较旧、新 parser 生成的 UAST 是否存在信息损失。这时必须：

```text
只给生成器 UAST
不能把原始 Python 源码同时给它
```

否则 UAST 即使丢失了信息，模型也可以从原源码中把答案补回来，测试就失去意义。

严格测试流程：

```text
原始源码 S
  → 旧 parser → UAST_old → 同一个 Python 生成器 → Source_old
  → 新 parser → UAST_new → 同一个 Python 生成器 → Source_new
```

生成器只能看 UAST。随后比较 Source_old 和 Source_new 的可解析性、重新解析后的 UAST、运行行为和信息损失报告。

### 4.2 实用型跨语言翻译：原源码可以作为辅助

如果目标是尽可能生成高质量的 B 语言程序，可以同时提供：

```text
原始源码
+ UAST
+ DL Semantic Profile
```

因为原源码中可能存在 UAST 没保留的注释、类型提示、字符串形式和框架线索。

但实验报告必须区分：

```text
UAST-only：检验 UAST 表达能力。
Source+UAST：检验工程翻译效果。
```

不能把 Source+UAST 的好结果宣称为 UAST 自身没有信息损失。

## 5. 那些大型仓库到底用来做什么

深度学习仓库在项目中有四个角色。

### 5.1 API 知识库

模型需要知道各框架如何表达同一个概念：

```text
Tensor 创建
矩阵乘法
卷积
激活函数
模型加载
设备选择
训练/推理切换
```

框架源码、文档和 examples 提供真实 API 证据。

### 5.2 测试程序来源

框架自身的 tests 通常包含大量小型算子测试：

```text
给定输入
执行一个算子
断言输出
```

这类测试比随意生成代码更适合作为跨语言差分测试种子。

### 5.3 目标运行环境

生成 Java/DJL 代码后，需要真正用 DJL 执行；生成 GoMLX 代码后，需要真正用 GoMLX 执行。仓库不是只拿来阅读，也提供构建、测试和运行依赖。

### 5.4 Bug 历史与回归样例

仓库的 issue、修复提交和 regression test 可以告诉我们：

```text
过去哪些算子出过错
哪些 shape/dtype/device 组合风险高
修复前后行为有什么变化
怎样构造最小复现
```

这些历史样例可以用于检验差分测试系统是否真的有发现能力。

## 6. 不是把整个框架互相翻译

下面这个目标不现实：

```text
整个 PyTorch 框架源码
→ UAST
→ 整个 GoMLX 或 DJL 框架源码
```

原因包括：

- PyTorch 内部有大量 C++、CUDA 和生成代码；
- 不同框架的架构和运行时完全不同；
- Python 动态对象与 Java/Go 静态类型不能机械对应；
- 框架底层依赖不同硬件和编译器；
- UAST 是程序分析 IR，不是完整编译器 IR。

真正可行的是翻译“调用框架的用户程序”：

```text
模型定义
Tensor/算子组合
预处理
推理流程
有限训练流程
测试断言
```

## 7. 从小到大的测试层次

### 7.1 Level 1：单算子

例如：

```text
加法、乘法、矩阵乘法
reshape、transpose
sum、mean、max
ReLU、Sigmoid、Softmax
卷积、池化、归一化
```

输入小、运行快、失败容易定位。最适合第一阶段。

### 7.2 Level 2：算子组合

例如：

```text
MatMul → Add → ReLU
Conv → BatchNorm → ReLU
Embedding → Attention → Linear
```

用于发现广播、shape、布局和默认参数组合问题。

### 7.3 Level 3：模型子模块

例如：

```text
一个残差块
一个注意力层
一个编码器层
一个简单分类器
```

### 7.4 Level 4：小型完整模型

例如：

```text
两层 MLP
小型 CNN
小型 Transformer
```

不建议一开始运行大模型训练，因为变量太多，失败难以定位。

### 7.5 Level 5：训练与梯度

最后再比较：

```text
loss
参数梯度
一次优化器更新后的权重
多轮训练收敛趋势
```

训练语义比推理复杂，应该在前四层稳定后开展。

## 8. UAST 在中间起什么作用

如果直接做：

```text
Python 源码 → Java 源码
```

模型容易只做表面文本翻译，很难知道转换失败发生在哪里。

使用 UAST 后，可以分开检查：

```text
源码解析是否正确？
函数和数据流是否保留？
算子调用是否被识别？
目标语言代码生成是否正确？
目标库 API 映射是否正确？
运行结果是否一致？
```

UAST 提供程序结构：

```text
变量
赋值
函数
调用
参数
返回值
分支
循环
类和成员访问
```

DL Semantic Profile 再提供：

```text
这是哪个深度学习算子
Tensor 的 shape/dtype/device
默认参数
训练还是推理
是否需要梯度
```

两者结合，才能比较可靠地跨框架生成代码。

## 9. 测试的意义到底大不大

如果只是把整个仓库丢给大模型，然后看生成代码“像不像”，意义很小。

如果满足以下条件，测试有明确研究价值：

```text
每个测试有明确数学语义；
输入、权重、shape、dtype、device 固定；
多个框架生成代码可编译、可运行；
有独立参考实现或 ONNX/NumPy oracle；
输出差异有数值容差；
失败可以缩小成最小复现；
能区分生成器错误和框架错误。
```

它可以衡量：

- UAST 对程序语义保存得是否充分；
- 大模型跨语言代码生成是否可靠；
- 不同深度学习库 API 是否语义对齐；
- 同一算子在不同后端上的数值一致性；
- 特定 shape、dtype、设备组合下是否存在实现异常。

## 10. 怎样判断是不是框架 Bug

假设结果是：

```text
PyTorch：0.8123
DJL：    0.8122
ONNX：   0.8123
GoMLX：  2.4178
```

不能立刻说 GoMLX 有 bug。调查顺序应为：

```text
1. 检查生成的 Go 代码是否表达相同操作。
2. 检查矩阵维度、数据布局和广播规则。
3. 检查 dtype、设备与默认参数。
4. 检查训练态、推理态和随机种子。
5. 与 NumPy 或手工参考公式比较。
6. 把失败程序缩小到一个或几个算子。
7. 在固定框架版本上重复运行。
8. 确认只有目标库稳定偏离后，才标记为 bug 候选。
```

还应注意：如果两个语言框架最终使用同一个底层引擎，例如都调用同一 ONNX Runtime，它们并不是完全独立实现。它们结果一致只能证明调用和封装较一致，不能充分交叉验证底层算子实现。

## 11. 具体应该先做什么

### 第一步：Python 自己还原自己

```text
Python 源码
→ Python UAST
→ 只根据 UAST 生成 Python
→ 重新解析
→ 比较 UAST 和运行结果
```

这一步验证 UAST 是否丢信息。

### 第二步：选择基础算子集合

建议首批：

```text
Tensor 创建
加法/乘法
矩阵乘法
reshape/transpose
ReLU/Softmax
sum/mean
```

### 第三步：建立 DL Semantic Profile

对每个测试记录：

```text
操作
输入值
shape
dtype
device
参数
期望输出或参考实现
```

### 第四步：选择一个目标框架

优先建议：

```text
Python/PyTorch → Java/DJL
```

因为 DJL 有清晰 Java API、YASA 已支持 Java，并且可以借助 ONNX Runtime 做共同参考。

也可以选择：

```text
Python/PyTorch → TypeScript/WebDNN
```

但这更偏模型推理和浏览器后端，不适合先做完整训练转换。

### 第五步：再引入大模型

先有确定性 PythonEmitter、测试规范和验证器，再训练大模型处理复杂 API 与跨语言生成。否则模型输出错误时没有可靠裁判。

## 12. 最终建议的数据流

```text
框架官方 examples/tests/历史 bug
            ↓ 提取小型可执行测试
原始 A 语言测试程序
            ↓ YASA Parser
Canonical UAST
            ↓ 深度学习语义识别
UAST + DL Semantic Profile
            ↓ 大模型/确定性生成器
B 语言 + 目标库测试程序
            ↓ 编译和重新解析
UAST round-trip / 结构检查
            ↓ 固定输入执行
输出、shape、dtype、梯度差分
            ↓ 异常最小化
翻译错误 / 配置差异 / 框架 Bug 候选
```

## 13. 一句话理解

> 仓库不是整包喂给模型去互相翻译，而是用来提取 API 知识、官方测试和历史 bug；大模型主要接收小型测试程序的 UAST、深度学习语义和目标库要求，生成另一语言的可执行测试程序，再通过多框架运行结果判断功能是否一致。
