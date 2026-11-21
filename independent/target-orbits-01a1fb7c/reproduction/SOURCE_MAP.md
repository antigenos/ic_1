# 从 DATE 原算法到 TCJAP 重建版

设真实输入数为 k，真值表有 N = 2ᵏ 行。一个内部信号有 m 行取 1，折叠计数 a = min(m, N−m)。本研究的目标是在实现相同输出真值表的所有合法电路中，最小化内部信号的 2a(N−a) 之和。输出门免费，固定目标本身的活动度为常数。运行效率按完成整个精确搜索的外部经过时间计算。[DATE 原论文](https://doi.org/10.23919/DATE69613.2026.11539139)

| 原件中的问题或步骤 | 锁定版源码中的位置 | 本次重建的证据 |
|---|---|---|
| DATE 第 II 节的活动度与输出极性 | `PexaManGetAct` 读取每个收费门的 minterm 变量，`PexaManPrintSolution` 恢复输出极性 | `tools/witness.py` 逐门逐行重算，并检查库中操作、拓扑和总活动度。0189 的互补归一目标为 FE76 |
| DATE 第 III 节的功能与拓扑编码 | `PexaManMarkup` 建立选择变量。每个门两端选择恰好一个前驱，源对象编号满足 0 端大于 1 端。`PexaManAddCnfStart` 要求每个应使用的源对象至少有一次使用。`PexaManAddCnf` 添加非零行 | FE76 见证直接在这套原 CNF 上用原 BSAT 做单元传播，读取当前轨迹和未赋值文字 |
| 内部门计数及公式 (8) 的加权和 | `PexaManAddPClausesBdd` 建立单门计数域。`CalculateBddCuddSmallerThanMin` 为活动度窗口构造 BDD，`ExaManAddCardClausesCudd` 加入 SAT | `variants/compositions.patch` 保持进入 BDD 构造器的直方图次序和内容。855 个窗口与原枚举有序比对 |
| DATE 第 III-D 节的搜索策略 | `init.cpp` 将模式 0、1、2 分派到队列、自由和区间搜索。正式比较均用模式 2，初始步长 75。`PexaManExactPowerSynthesisBasePowerBDDBinaryInner` 逐项查询收费门数 r，管理器中总门数为 r+1 | 每次查询使用闭区间 [act,act+delta]，找到解后按整数除法更新 delta，再次搜索。外层在当前区间失败后增加 act。独立下界检查覆盖 96 和 0189 |
| 复盘中的慢基线 | 原版可在构造 BDD 前扫描 (r+1) 的 N/2 次幂个计数向量，要求计数之和为 r 且活动度在窗口内 | 0189 诊断记录拆分枚举、BDD 项、其余编码和 SAT 时间，工程候选只访问可行的弱组合 |
| 强化对照中的支持度剪枝 | 第 g 个收费门从零编号，最多依赖 min(k,g+2) 个主输入，因此 a 具有相应的二次幂整除性 | `variants/support.patch` 给不可能的单门计数添加单位子句。保留 DATE 的查询窗口和收费约定 |
| TCJAP 第 4 节的目标行关系 | 公开核心 `p9_joint_support` 接收有序前驱的行掩码、操作掩码、计数域、收费位及剩余预算 | 本次直接编译固定的 MIT 核心。独立的完整真值向量枚举验证 FE76 及三个邻近对照，另复跑公开检查器 |
| TCJAP 第 4–5 节的传播与解释 | 公开发布物披露局部关系和统计汇总，完整 SAT 接线和原始轨迹未发布 | `tools/joint_trail.h` 从当前 SAT 轨迹提取事实，扣除其余门的安全下界，构造有效解释。`tools/trail_clause.h` 选择监视文字、登记理由并入队。`tools/audit_trail.py` 从实际理由文字独立核验 |
| 一端已选和两端已选的区分 | 一端已选时，空支持删除另一端的候选连接。两端已选时，投影后的计数值无支持可被排除 | `early`、`counts`、`both`、`off` 以及局部预算开关控制同一构建，独立计时和解释记录分别保存 |

锁定的文件入口包括 [DATE 插件实现](https://github.com/cda-tum/ext-pexact/blob/7253861c224e7c9de2c802e61c86f89338253544/pexact.c)、[命令行分派](https://github.com/cda-tum/ext-pexact/blob/7253861c224e7c9de2c802e61c86f89338253544/init.cpp)、[ABC 的 BSAT](https://github.com/allen1236/abc/blob/c851fce40d9dde1aaf32b087a0f449751ea070dc/src/sat/bsat/satSolver.c)、[TCJAP 局部核心](https://github.com/qmkkk/TCJAP/blob/59e5a0e954d6a0a6711b2bdc9898db875ede6889/src/joint_relation.c) 和[发布范围](https://github.com/qmkkk/TCJAP/blob/59e5a0e954d6a0a6711b2bdc9898db875ede6889/CORE_PROVENANCE.json)。

## 比较口径与已知实现差异

- DATE 论文描述了面积最优电路提供搜索上界的用途。锁定版模式 2 的实际入口从 act=0、步长 75 开始，使用 `CalcMaxAct` 判断应检查哪些门数。本实验保留该实现。
- TCJAP 手稿描述了对已经选中且无支持的计数立即返回冲突。本次集成只推导尚未赋值文字，为它们加入有效理由，余下冲突由原版布尔求解器处理。只在理由的最高前提层与当前决策层相符时入队。
- 手稿描述其早期连接推理最多处理 16 门。重建版沿用原插件的对象数组界限，未另加 16 门开关。手稿所述的历史实现也会区分纯功能理由和预算理由。本次在启用预算时允许理由带上更多已成立前提，并逐条验证。它们保持有效性，可能改变搜索轨迹和运行时间。
- 手稿的 R/E 消融在包含门局部传播与联合预算等机制的共用配置上进行。本次开关隔离整个已选对计数过滤、提前连接排除和局部预算，分母以本次运行清单为准。两套消融的数值分别解释。
- 公开汇总将 71、73、94 对应到作者工程版、强化对照和完整方法。本次首列为原作者固定源码。硬件、操作系统、集成和未公开的历史运行器也有差异。[TCJAP 公开统计](https://github.com/qmkkk/TCJAP/blob/59e5a0e954d6a0a6711b2bdc9898db875ede6889/data/experimental_scope.json)
