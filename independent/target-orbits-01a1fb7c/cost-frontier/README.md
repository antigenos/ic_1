# 四输入布尔函数最小开关活动度的精确证书

在 DATE 2026 的门库与活动度定义下，完成了 ABC 全部 **208 个四输入全依赖 NPN 类**的精确综合。每类均有达到下界的电路。固定的上一轮强化版在每类 300 秒的时限内完成 91 类，本轮补齐了余下 117 类。208 类共同建库的用时和 208 次冷启动的用时分别记录。成果包括可执行算法、作者求解器接线、逐类电路、直接对照和真实设计的反例。[逐类最优值与电路](evidence/residual-projected/audit.json) · [从原始记录重新计算的汇总](evidence/verified-release.json)

## 新的研究结果

一个目标真值表给定后，末门的一根输入线会限制另一根输入线上哪些行必须为零或一。由这些行约束可以算出另一个输入至少要付的活动度。沿搜索第一次越过预算的位置，记录每类已知输入线的最低到达成本，把它与末门伙伴的最低成本合并，就得到对**尚未搜索部分**的下界。有些电路的最优代价高于已完整遍历的预算，仍可提前证明最优。在三输入预算 56 上，两种方法访问同样的 202 个带标号状态，普通下界证明了 12/14 类，目标相关下界证明了 14/14 类。[推导及最接近工作](METHOD.md) · [小规模穷举](small.json)

四输入整库使用同一条不等式继续剪枝。对尚未解决的每个目标，以当前可行解给出待排除的最高代价，再把所有目标对某一类末门输入的限制合并成一个数。每加一根线即可判断该分支是否还有可能改进任何待解目标。预算由程序从本轮已找到的电路选择，冷启动输入是变量数、起始预算和模式。520 的起始预算是依据先导实验选出的。[逐分支推导](RESIDUAL.md) · [自动搜索实现](refine.cpp)

Knuth 和 Goucher 已研究按门数构造布尔电路库。Goucher 已公开可达真值表集合、整体输入对称性和可删除末端剪枝。DATE 提供开关活动度目标与 SAT/BDD 搜索。TCJAP 将前驱和活动度预算联系起来做局部传播。本项目的贡献是跨搜索边界的目标相关活动度证书，以及它对剩余分支的排除作用。对照实现复用了上述已有的集合与剪枝技术。查新截至 2026-11-24，范围以所列原始论文、程序和公开检索为准。[DATE 原文](https://www.cda.cit.tum.de/files/eda/2026_date_exact_synthesis_with_optimal_switching_activity.pdf) · [TCJAP 作者代码](https://github.com/qmkkk/TCJAP) · [Goucher 原文](https://cp4space.hatsya.com/wp-content/uploads/2023/03/sfobc_transcript.pdf) · [Knuth 程序](https://cs.stanford.edu/~knuth/programs.html)

## 三种比较

| 要回答的问题 | 同等任务和对照 | 实测结果 |
|---|---|---|
| 新的分支规则是否有独立作用 | 同一二进制、逻辑核 16、相同前缀、候选上界和终止条件，仅切换目标相关剪枝 | 208 类全部完成。普通规则 340.59 秒，新规则 73.58 秒。后段展开状态从 10,765,482 降至 1,427,146 |
| 和直接穷举相比是否值得采用 | 逻辑核 20 先运行带末端剪枝的直接法，免费提供恰好覆盖整库的最小预算 662。候选自动选到 670。两者均从零构造整库 | 220.22 秒对 59.05 秒，单次同核对照为 3.73 倍。峰值工作集分别为 452.5 和 115.7 MiB |
| 能否回到作者入口取得合格电路 | 一个冷启动 ABC 进程逐个执行 208 条 pexact 模式 2 命令，共享一次构库；由原功能和计数 CNF、TCJAP 传播及原 SAT 求解器确定连接和门类型 | 66.54 秒完成，逐门逐行外部重算后合计 67.83 秒。全部目标的真值表、门库、输入使用和活动度通过 |

不同次运行的墙钟受主机负载影响。较早的直接法耗时 126.38 秒，状态数与同核确认完全一致。旧版 91/208 的统计采用每个目标单独限时的口径；据此计算完成数增量。最难的两例是 1681 和 1698，最优值分别为 662 和 630。[同核直接法](evidence/matched-direct/result.json) · [同核候选](evidence/matched-projected/result.json) · [关闭分支规则](evidence/residual-uniform/result.json) · [作者入口的 208 份原始输出](evidence/author-fixed/solver.log) · [旧基线](../evidence/full-300/summary.json)

直接搜索和候选使用不同的停止规则，共用部分真值表运算和对称性代码。为排查共同错误，独立构造了 384 个群作用在全部 32,768 个正规化真值表上的映射，并穷举 7,241,507 对操作数复核全部 49,062 个伙伴代价。四档预算下的 888 个下界记录均重新算得一致。历史两组 SAT 合计覆盖的 93 个不同目标也逐一相符。[有限域复核](evidence/finite-audit.json) · [复核程序](validate_proof.py)

## 真实电路中的收益与代价

EPFL 的三个原始 AIG 先用固定 ABC 映射成四输入 LUT，再将全部四输入全依赖节点分别替换为最小活动度电路和 ABC twoexact 按最小门数返回的首个电路。其余 LUT 保留。两种替换在三个设计上均通过原 AIG 对整网的组合等价检查。局部指标采用 DATE 的独立均匀输入模型。整网稳定翻转使用每个设计固定的 65,536 个伪随机主输入向量，统计相邻向量的零延迟节点翻转。[映射、逐类结果和六份 CEC 输出](evidence/epfl-cut-check.json) · [稳定翻转记录](evidence/stable-transitions.json)

| 设计 | 替换 LUT 数 | 局部活动度，面积优先 → 活动度最优 | 展开门数 | 整网稳定翻转变化 |
|---|---:|---:|---:|---:|
| 加法器 | 128 | 46,990 → 41,740 | 554 → 639 | +5.45% |
| 优先编码器 | 198 | 49,824 → 44,590 | 721 → 848 | −10.54% |
| 路由器 | 53 | 10,664 → 9,934 | 164 → 177 | −17.32% |

共 379 个 LUT，均匀局部活动度合计下降 10.43%，展开门数由 1,439 增至 1,664。加法器给出了明确的适用边界，均匀局部最优可以伴随整网稳定翻转上升。真实工艺的负载、门延迟和毛刺功耗尚待测量。

## 复现

下列 PowerShell 命令从仓库根目录执行。在 Windows 11、Python 3.12、MSYS2 UCRT64 GCC/G++ 16.2.0 上完成验证。生成结果放在新目录，保留已有运行记录。

```powershell
$d = 'independent/target-orbits-01a1fb7c/cost-frontier'
python "$d/verify_release.py"
python "$d/small.py"
New-Item -ItemType Directory -Force .local | Out-Null
g++ -std=c++20 -O3 -DNDEBUG -march=x86-64-v2 -static "$d/refine.cpp" -o .local/refine.exe
python "$d/run.py" .local/refine.exe 4 auto projected .local/replay-full --seed 520
python "$d/audit.py" .local/replay-full/table.tsv --out .local/replay-full/audit.json
```

要运行作者入口，先按锁定的上游构建说明准备 ABC 目标文件，再执行以下命令。最后一条在指定逻辑核运行；核编号按本机可用核选择。[上游构建说明](../reproduction/REPRODUCTION.md) · [DATE 到 TCJAP 的公式与代码对照](../reproduction/SOURCE_MAP.md)

```powershell
python independent/target-orbits-01a1fb7c/build.py
python "$d/build_bridge.py"
python "$d/author_batch.py" .local/replay-full/audit.json .local/replay-author --cpu 0
```

单独调用该二进制时，设置 `PEXACT_FRONTIER_CAP=520` 和 `PEXACT_FRONTIER_COMPLETE=1` 启用完整共享搜索。原有四输入模式可关闭本研究选项；其回归用例与三输入用例均已检查。固定真值验证使用作者的完整功能和计数约束，通过 SAT 后从模型重算活动度。保留 `PEXACT_FRONTIER_VERIFY=range` 供一般 BDD 回验。较早一次一般 BDD 批次在 64 例完成后由新验证器接替，0116 的旧回验耗时 103.00 秒。预算 580 的一次中断只留下启动凭据，另存的完整运行用于结果分析。[原 BDD 验证日志](evidence/author-batch/solver.log) · [固定真值核查](bridge.h) · [预算与运行登记](EXPERIMENT.md)

从同一份新表复算应用实验时，`circuits.py` 会核对或下载固定版本的三个 EPFL AIG；`transitions.py` 读取生成的 BLIF。输出文件名决定工作目录，所以请为每次完整重跑指定新名字。

```powershell
python "$d/circuits.py" .local/replay-full/table.tsv .local/replay-epfl.json
python "$d/transitions.py" .local/replay-epfl .local/replay-stable.json
```

本项目的研究判断是，四输入精确综合范围内已有可独立成文的算法贡献，具备以中科院二区期刊为目标的创新与验证依据。分区属于期刊，最终学术评价取决于同行评审。本轮交付限于研究结果和复现材料。
