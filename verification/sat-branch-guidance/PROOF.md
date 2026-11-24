# 独立最优性证据

沿另一条已归档的验证线检查了四输入全族穷举。远端可达提交 `5400328802c98c1870fb7f61ff2475f698ee48ea` 的 `research/interval-proof-9720/evidence/family-bounds-432.json` 对应 Git blob `5e60e50a21dd94da0c10247066785e45b478dd59`。同目录 `family_bounds.py::enumerate_bounds` 独立于 BSAT，枚举已付费的不同内部真值向量集合。每步枚举两种不同可用信号的五种门结果，累加新信号费用。任意重复向量都可直接复用早先节点。额外允许免费零信号，放宽了原电路集合，因此所得最小费用是原问题的下界。严格小于 432 的 2,243,437 个状态均已检查可否用一个免费输出门结束。这一证据可以复用。

开发三类的下界依次是 304、310、344。预登记留出六类依次是 182、216、248、320、264、326。每个成功返回必须用 `tools/witness.py::simulate` 逐门模拟 16 行，核对输出、门库、拓扑、补相、使用约束及收费，再逐例与该下界相等才算验证最优。未结束的调用保持 timeout/unknown。

历史定点原始记录 `evidence/screen-traces/frozen-0189.log.gz` 在最初的两门、上界 150 查询中记录了两次有效连接排除、六次检查和一次冲突。单端选择后，原规则已可推出另一端的连接排除。这个历史轨迹说明为何输出排序可能起作用；三个策略的因果与代价以本轮逐查询诊断和完整计时判定。

[穷举程序](https://github.com/antigenos/ic_1/blob/5400328802c98c1870fb7f61ff2475f698ee48ea/research/interval-proof-9720/family_bounds.py) · [原始下界记录](https://github.com/antigenos/ic_1/blob/5400328802c98c1870fb7f61ff2475f698ee48ea/research/interval-proof-9720/evidence/family-bounds-432.json)
