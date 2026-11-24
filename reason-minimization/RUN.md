# 复跑和诊断边界

在本分支仓库用 Python 3.12+ 依次运行下列命令。Windows 冻结配置使用 MSYS2 UCRT64；TCJAP_REFERENCE 指向已按 REPRODUCTION.md 准备的只读冻结工作区，其中包含 joint、screen-short、ABC 原链接对象。tools/build_candidate_screen.py 的 short 分支只用作来源定位。

```powershell
python reason-minimization/simulate.py
python reason-minimization/build.py
python reason-minimization/panel.py trace audit-01
python reason-minimization/panel.py profile profile-01
python reason-minimization/panel.py timed paired-01
```

每个目录名只用一次；诊断出错须先检查原始日志。物理核监视器复用同仓库另一独立检查点 3705fbc086f28aedd996061f6c7a7d6f8d340632 的 research/discrete-budget/guard.py，每 0.2 秒检查其他 ABC 和已绑核 Python 控制器。需在主机进程可见的环境启动。0020 等其他输入未登记。四个正式实例都以 60 秒为限。006b 的既有冻结结果未在 300 秒内完成，诊断对其取累计生成至少 2048 条传播原因后第一个完整查询边界，全量核对该前缀；其余三个函数取完整轨迹。诊断各有 300 秒保护限时。前缀以退出码 77 标记，独立于正式时间和求解状态。

WORK 行依次为本次查询的冲突、决策、布尔传播、计数/连接原因构造尝试、计数/连接构造及入队的 QPC ticks、每秒 ticks、计数/连接回用次数。额外支持核调用数在源码路径上恒为零。profile 关闭逐条日志；每个计时窗口包括两个时钟读取的测量扰动。正式 online 完全编译去除诊断。短子句可能原样成为后续冲突；三文字及以上用实际句柄、数据库搬迁映射和文字集合核对来源，二元监视单列同内容事件。

最优性依据取同仓库 5400328802c98c1870fb7f61ff2475f698ee48ea 的 research/interval-proof-9720/evidence/family-bounds-432.json，对严格费用低于 432 的 2243437 个放宽电路状态已穷举。本轮只读取输入对应的下界，与完整求解返回的独立真值和费用重算相合才记作最优。下界单独不能为超时提供可行电路。

构建故障记录：第一次在含中文的绝对路径上汇编时未能创建 pexact.o。改用相对于 ABC 根目录的路径再编译；原失败未启动求解。
