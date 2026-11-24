# 精确综合中门数与翻转活动量的权衡

研究沿 Walter、Feldmeier 和 Wille 的 DATE 2026 模型及 TCJAP 的公开核心继续推进。单输出电路使用任意二输入逻辑门，边可以免费取反。理论部分假定相邻输入字独立且均匀。内部节点在 N 行真值表中有 p 个 1 时，收费为 2p(N−p)。门数计入输出门，活动量不计输出门，因为所有实现的输出函数相同。[原始研究与 TCJAP 复现](../../../REPRODUCTION.md) · [上一轮四输入完整最优库](../FINAL.md)

## 发现与证据

对任意两组互不重叠的变量，考虑“第一组全部成立，第二组至少一个成立”。令组的大小为 q、k，二者至少为 2，n=q+k。这是一个子立方体删去一个点后的布尔函数。我们给出它的完整门数–活动量帕累托前沿。最少门数为 n−1。在所有最少门数电路中，最低活动量等于两组分别组成链再合并的代价。再加一个门，复用第一组的结果计算完整反例，再从第一组的结果中扣除该反例，即可达到所有二输入 DAG 的全局最优。两组等大且持续增长时，相对最佳最少门数实现的活动量降幅趋近 50%。[任意输入规模的证明与预登记](PARETO.md)

| 两组输入数 | 最少门数下的最低活动量 | 多一个门后的全局最低活动量 | 降幅 |
|---|---:|---:|---:|
| 2 + 2 | 192 | 182 | 5.21% |
| 3 + 2 | 992 | 790 | 20.36% |
| 3 + 3 | 4864 | 3286 | 32.44% |
| 4 + 4 | 93184 | 54102 | 41.94% |

证明进一步刻画了任意 n≥4 时全支撑函数最低两个活动量层中的所有等价类。对五、六输入预留预算，前向真值信号集搜索和后序表达式搜索各自独立枚举了完整子水平集，每组 16 个等价类的最优值逐一相同。四输入全部 65,536 张带标号真值表覆盖 416 个可识别目标。候选方法还通过原生 TCJAP 重建版的普通命令入口，416 个目标的输出电路全部逐行核对。[四至八输入的树形最优对照](evidence/pareto-audit.json) · [五输入独立搜索](evidence/postfix-held-5-1050-2.json) · [六输入独立搜索](evidence/postfix-held-6-3664-2.json) · [原生命令核验](evidence/native-entry.json)

前缀连通性剪枝在预留五输入实验中将访问状态从 549 减至 502，六输入从 339 减至 338。冷启动总耗时未体现稳定优势。研究价值主要来自可证明的全局最优结构与可执行的精确构造。[推导、消融与准入记录](STUDY.md)

## 从局部最优到整机验证

20 个 EPFL 标准规模电路中，18 个包含可替换区域，共命中 11,047 处。初次按均匀、独立的局部输入进行替换，各区域的预期单位翻转之和下降 12.89%，但按整机主输入激励实测，全网翻转从 700,123,458 增至 705,047,264，增加 0.70%。内部信号之间的相关性会改变两种结构的优劣。[原始登记](APPLICATION.md) · [含反向结果的全部记录](evidence/epfl)

修正后先用 2,048 对主输入训练。在逻辑深度限制下，对照组搜索每个目标的全部最少门数树；候选组可再选择共享中间结果的链并优化各组输入顺序。每个替换区间的外部信号完全保持，因此不同区间的翻转变化在同一组输入上可以逐项相加。独立程序在 394 项成本与时限检查中找到了相同的最优解。最终 8,192 对主输入未参与选择。[阶段 14 修正规则](TRANSFER.md) · [精确动态规划](correlated.py) · [小规模独立核验](evidence/correlated-small.json)

| 20 个设计合计 | 原始 AIG | 按训练数据优化的最少门数对照 | 增加共享选项 |
|---|---:|---:|---:|
| AND 节点数 | 462,884 | 462,884 | 465,517 |
| 留出集全网翻转次数 | 1,400,374,454 | 1,393,414,464 | 1,384,819,938 |

新增 2,633 个 AND 节点（0.569%），比同门数对照少 8,594,526 次翻转（0.617%），比原始电路少 1.111%。相对同门数对照为 9 个改善、11 个持平，各设计深度均相等；相对原始设计为 17 个改善、3 个持平。8 个留出面板的独立增益范围为 0.615%–0.619%。除法器贡献了绝对增益的 77.1%，存储控制器贡献 20.0%。去掉除法器后，剩余 19 个设计合计相对对照下降 0.163%。全流程计时合计 160.22 单核墙钟秒，其中两种结构的选择耗时 9.71 秒。每份记录含面积、深度、训练与留出计数及等价性结果。这里测量稳态逻辑翻转与 AND 层数，实际芯片功耗、毛刺、单元面积及布局后时序需要各自的实现证据。[逐电路原始结果](evidence/transfer) · [完整审计与汇总命令](summarize.py)

## 与已有工作的关系

DATE 的位置活动量下界、TCJAP 的目标条件局部可行性、布尔链分类及只读一次的树形枚举均有直接先例。经典低功耗综合已经通过改变门树或增加冗余连接降低翻转。这里提出的可核查区别是对这个无限函数族给出两个精确目标值，比较对象包括所有最少门数实现和所有允许共享的 DAG，并完整分类最低两层。动态规划额外处理同一整机输入造成的联合转移和到达时间约束。已查一手来源中未见相同定理；查新范围限于可检索公开工作。[DATE 原文](https://www.cda.cit.tum.de/files/eda/2026_date_exact_synthesis_with_optimal_switching_activity.pdf) · [TCJAP 作者公开核心](https://github.com/qmkkk/TCJAP) · [Wang 与 Vrudhula 的冗余连接算法](https://www.cecs.uci.edu/~papers/compendium94-03/papers/1996/iccad96/pdffiles/05a_3.pdf) · [Zhou 与 Wong 的低功耗门树精确分解](https://www.cs.utexas.edu/ftp/techreports/tr97-21.pdf) · [Panda 与 Najm 的活动量驱动分解](https://www.ideals.illinois.edu/items/100306/bitstreams/320399/data.pdf)

## 复核与运行

从仓库根目录运行。第一条只读保存的证据并重算费用表、对照和基准汇总。第二条直接生成六输入例的两个端点。Python 使用标准库。真值表按十六进制输入，最低位对应全零输入，变量 0 变化最快。

```powershell
$study = 'experiments/fixed-fanin-01a1fb7c/support-frontier'
python "$study/summarize.py"
python "$study/synthesize.py" 6 7f
g++ -O3 -std=c++17 "$study/frontier.cpp" -o .local/frontier.exe
g++ -O3 -std=c++17 "$study/postfix.cpp" -o .local/postfix.exe
python "$study/run.py" .local/frontier.exe 6 3664 2 .local/fresh-six.json --cpu 24
python "$study/crosscheck.py" .local/postfix.exe .local/fresh-six.json .local/fresh-six-check.json
```

原生入口先按仓库复现说明构建固定版本 ABC 及 TCJAP 公开核心，随后运行以下命令。四输入识别命中后会调用原作者的 SAT 固定拓扑检查并打印电路。其他四输入函数进入冻结的 TCJAP 搜索。五输入以上走独立构造入口。完整同预算穷举支持至六输入，解析构造对显式给出的更高输入数真值表也适用。

```powershell
python "$study/build_native.py"
& .local/variants/fixed-fanin-pareto/abc.exe -c 'pexact -I 4 -M 2 0007'
python "$study/native_acceptance.py" .local/variants/fixed-fanin-base/abc.exe .local/variants/fixed-fanin-pareto/abc.exe .local/fresh-native.json
```

整机实验读取 EPFL 官方提交 `82d8cc6910419298e713a46644ed59fd3df53038` 的 `arithmetic` 和 `random_control` 两个目录内全部 AIG 文件。下列命令按次序使用同一份输入和新的输出目录。原始运行使用逻辑 CPU 24。独立验证器逐对检查电路输出，整机等价性另由 ABC 的 CEC 检查。[EPFL 基准](https://github.com/lsils/benchmarks/tree/82d8cc6910419298e713a46644ed59fd3df53038)

```powershell
git clone --depth 1 https://github.com/lsils/benchmarks.git .local/epfl-replay
git -C .local/epfl-replay fetch --depth 1 origin 82d8cc6910419298e713a46644ed59fd3df53038
git -C .local/epfl-replay checkout --detach 82d8cc6910419298e713a46644ed59fd3df53038
$epfl = '.local/epfl-replay'
$abc = '.local/variants/fixed-fanin-base/abc.exe'
python "$study/application.py" $epfl $epfl $abc .local/fresh-uniform-aigs .local/fresh-uniform-results
python "$study/verify_correlated.py" .local/fresh-dp-check.json
python "$study/workload.py" $epfl $abc .local/fresh-profiled-aigs .local/fresh-uniform-results .local/fresh-profiled-results
```

## 检查点

GitHub 专用分支为 `codex/support-frontier-01a1fb7c`。下列提交分别保留理论预登记、独立证明核验、原始反向结果和修正后的方法，便于按阶段恢复工作。

| 可回退状态 | GitHub 提交 |
|---|---|
| 原始研究和四输入最优库 | [f4c919e](https://github.com/antigenos/ic_1/commit/f4c919ecc11f5221b6a80db26c66352efcca3211) |
| 首轮问题、下界和保留集登记 | [a009480](https://github.com/antigenos/ic_1/commit/a00948085a38e5f4a533f9c72226e286d86cbfed) |
| 帕累托证明、保留集及独立搜索 | [04e2c95](https://github.com/antigenos/ic_1/commit/04e2c95a153dfc02a601fd80a6ed3baf999a96ab) |
| 原生 TCJAP 接入和首次整机负结果 | [fc1e4e3](https://github.com/antigenos/ic_1/commit/fc1e4e359fd44a74144961be6494a6df7bad8800) |
| 新训练集、留出集及对照预登记 | [5ad40a6](https://github.com/antigenos/ic_1/commit/5ad40a66401e5c3ea792fe9910f28703158064ba) |
| 相关输入优化器和独立小规模核验 | [5f92146](https://github.com/antigenos/ic_1/commit/5f9214638818924657baa79d1473a8576a68a573) |
