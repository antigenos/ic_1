# Reusing certified activity windows in pexact

本目录属于 DATE 2026 → TCJAP 独立复现的后续对照，使用原门库、目标真值与活动度模型。公开分支为 `codex/interval-proof-9720`。研究代码及实验只写入此目录。基础代码取本分支的初始提交 `afdbfca6d28e246b085e97d6da57f22ef0fd80b8`。

## 已有复现

完整复现本地冻结为 `365a8db35e39918d10e9a16cec1495611dd5e0d0`，与其公共历史镜像 `e1c19a7355b4d073280d57684d571f179fa8d717` 的文件树相同。根目录的 SOURCE_MAP.md、REPRODUCTION.md、THIRD_PARTY_NOTICES.md 提供源码映射、构建命令及许可。final-reproduction.zip 存放相对公共起点新增的三版 208 类原始结果、完整消融、独立审计及最终研究记录。压缩包内路径与冻结版一致。每例 300 秒，原版、强化版和重建版分别完成 67、72、80 类；历史参照为 71、73、94。原论文及作者核心分别见 [DATE 全文](https://www.cda.cit.tum.de/files/eda/2026_date_exact_synthesis_with_optimal_switching_activity.pdf) 和 [TCJAP 源码](https://github.com/qmkkk/TCJAP/tree/59e5a0e954d6a0a6711b2bdc9898db875ede6889)。

## 本轮研究登记

阶段 1–7 沿用冻结复现。阶段 8 只检验作者 mode 2 的一个调用链。PexaManExactPowerSynthesisBasePowerBDDBinaryInner 在得到 SAT 见证后缩小窗口，将门数循环从头开始；外层又按缩小后的步长推进。PexaManAlloc、ExactPowerSynthesisCnfBddRange 和 BSAT 的完整开销可能因此重复。阶段 9 假设针对固定目标、门库、输入数和收费门数，每个真正返回 UNSAT 的闭区间可为后续查询提供无解证据。另可用逐门支持度允许的折叠计数做整数加和，计算松弛后仍可能出现的总分。构造失败、求解 UNKNOWN 以及 SAT 未找到更低解均不能登记为 UNSAT。原算法已有逐窗口枚举，固定窗口的预算传播已在 TCJAP 中验证。跨迭代复用知识在增量 MaxSAT 中已有系统研究，本轮仅检验目标编码和折叠计数支持结合后的实际效果。[增量基数约束原文](https://arxiv.org/abs/1408.4628)

阶段 8 最小诊断先采集 0189 冻结代码的窗口、门数、状态与耗时。如果真实轨迹无重复证明且可实现分值无法排除窗口，就保留负结果。若有可排除工作，先枚举核验，再在相同入口验证。主要指标是完整最优求解的墙钟、固定上限完成数和独立见证。按同一逻辑核心、ABBA 反序比较 0189、此前比强化基线慢的 001e、以及编号相邻的 018b。前两例各限 30 秒，困难例各版 300 秒；困难例用两版各一次轮换。记录包括超时、不利实例和相同结果的重复性。候选初筛后再决定扩展规模。作者的全量复现数据已冻结。
