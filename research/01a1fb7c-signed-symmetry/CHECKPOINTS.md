# 可回退的研究版本

每次表中所列 GitHub 提交的完整树都与对应本地研究提交的树逐项匹配。网页提交和本地提交由两个身份分别创建，因此提交号不同。用 GitHub 提交号即可在新分支上检出相应文件，已有分支和 main 的历史都可以保留。

| 回退位置 | 本地提交 | 对应 GitHub 版本 |
|---|---|---|
| 冻结原论文到 TCJAP 的复现材料，保留作者、强化、重建三组基线 | e42d0b8 | [冻结副本](https://github.com/antigenos/ic_1/commit/500b0f7d3db677f7e30da87a66b85a7460f9021b) |
| 六例初筛、经典整链对照与负结果 | 452fe53 | [初筛完成](https://github.com/antigenos/ic_1/commit/89710071c7aee2c7c748f1356deea96fcb1153ea) |
| 锁定独立十二例和无符号消融，尚未使用它们的结果 | 8bd0df6 | [确认前版本](https://github.com/antigenos/ic_1/commit/ac2907c059eafd5b505a27be3277fa6e82d16ce5) |
| 恢复暂停实验、保留两个开发例的 SAT 搜索计数 | 0725b98 | [暂停恢复与归因](https://github.com/antigenos/ic_1/commit/b7bf5724792cfe8e19ef496b18a3ff93e75b9a7b) |
| 有限门数的投影预算下界通过数值核对 | c717d13 | [预算界](https://github.com/antigenos/ic_1/commit/a41e0fede22c64f7182070e7d3c845bc349d472e) |
| 原始首末门联合禁配在开发例上增加冲突，保留负结果 | 6d1af28 | [原始禁配的结果](https://github.com/antigenos/ic_1/commit/00f75062e0adad99e18febf7223ab2bb7fcec429) |
| 对称性十二例完成；冻结 H/N 比较和短子句消融 | 5a0e49d | [阶段 13](https://github.com/antigenos/ic_1/commit/ab68d5c21049bf0cbdd31853beae7779a0426098) |
| 锁定新的 F/H/N 全族清单 | 80320e1 | [208 例计时前版本](https://github.com/antigenos/ic_1/commit/cd8216329267342df56a63c5aff5957e28d30c93) |
| 完整未约化枚举交叉核对 82 个已有最优值 | 09d44af | [独立成本核验](https://github.com/antigenos/ic_1/commit/9de9c9efba79bb13d6d819f635f183e55f9d7aba) |
| 仅约化首门，上限 440 恢复原坐标 108 个电路 | 27c4bf6 | [首门轨道版本](https://github.com/antigenos/ic_1/commit/28e2514900ea5e75e919a2259936dc358f6bbfab) |
| 上限 500 恢复 150 个电路，锁定冷启动接入方法 | f76d55f | [扩大上限](https://github.com/antigenos/ic_1/commit/2babe33db857b216aa8bad4ec4d031eb762874a4) |
| 逐步约化，上限 560 核验 192 个电路及直接作者 SAT 对照 | 5a91a43 | [192 个电路](https://github.com/antigenos/ic_1/commit/e1f19c1ed8acd0f4c5ea6b81b387e524e1e4e1eb) |
| 接入完整见证，锁定独立冷启动样本 | 201e07a | [确认前的代码与清单](https://github.com/antigenos/ic_1/commit/9ee861866b9eca8df4efbf72a261dd92a5c595fa) |
| 单独运行 500 上限无约化对照，保留中断及异常计时 | 8f9375a | [无约化原始结果](https://github.com/antigenos/ic_1/commit/375f6eb03b5bc625a1b5e7be739ac5bbe654b128) |
| 将正式程序的选择器转换核对到 60,866 张不同真值表 | 7b7c735 | [输入排列和取反的覆盖](https://github.com/antigenos/ic_1/commit/f42f08816e4cf95c1fd5c4ab25833517d59ab8a8) |
| 确认 52 类最优 DAG 必须共享中间门 | a76784f | [无扇出公式的直接对照](https://github.com/antigenos/ic_1/commit/2488bb18efb3ddede480e8f8fa52ecce0761b782) |
| 全部 208 类取得可行上界，逐项核对公式表的递推不等式 | 7776baf | [余下 16 类的数值区间](https://github.com/antigenos/ic_1/commit/02505092c2a14bbc8e135bb7e12049adfedefd9f) |
