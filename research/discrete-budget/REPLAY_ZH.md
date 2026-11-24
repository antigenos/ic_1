# 复核与复跑

使用 Windows x64、Python 3.12 或更高版本（保留断言）、Git、MSYS2 UCRT64 GCC/G++；本次 GCC 16.2.0。窗口与原因独立检查器只需 Python 标准库。切到本目录前，从全新独立检出获取本线和被引用的外层源码对象。

```powershell
git clone --branch codex/verify-discrete-budget https://github.com/antigenos/ic_1.git discrete-budget-verify
cd discrete-budget-verify
git fetch origin refs/heads/codex/interval-proof-9720:refs/remotes/origin/outer-filter-study
git cat-file -t 5400328802c98c1870fb7f61ff2475f698ee48ea
cd research/discrete-budget
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PATH = 'C:\msys64\ucrt64\bin;' + $env:PATH
```

## 已归档数据

```powershell
python tiny.py
python tiny_even.py
python historical.py
python historical_reasons.py
python certificate_diagnostic.py
python summary.py dev2-three
python summary.py dev2-profile --diagnostic
python summary.py dev2-trace --diagnostic
python summary.py dev3-four
python check_trigger.py
python validate_confirmation.py confirm4 post4 --dest .local/recheck
```

historical.py、certificate_diagnostic.py 只读取公共筛选记录和另一分支的原始查询日志。historical.py 会暂存按查询分组的输入；首次在空目录复核时先运行 `New-Item -ItemType Directory -Force .local`。validate_confirmation.py 按每个 case 的验收标记选择计时组，逐次检查可执行文件哈希、同核顺序、原始返回电路与穷举下界；独立解码所有留出原因，逐查询复算外层 skip，并逐条比较 holes 与 trigger 的理由。源分支起点与作者基线构建见根目录 [REPRODUCTION.md](../../REPRODUCTION.md)，公式与入口见 [SOURCE_MAP.md](../../SOURCE_MAP.md)。

## 从源码重建求解器

用已经构建冻结 joint 的独立目录作为 BASE，只从中读取已准备的 ABC、公开核心和链接对象。本机使用只读参考检出 tcjap-replay。首次使用新主机时，在另一个独立检出按根目录 REPRODUCTION.md 构建 ABC 与 joint；输入三份归档的提交和摘要见 [sources.json](../../sources.json)，这包括 ABC 的 Windows 主机适配。然后指定该独立检出的绝对路径。下列 build.py 验证生成的 pexact.c 冻结指纹，仅在本线 .local 写入。复用原生源码和对象保留其许可与通知，作者 pexact 和公开局部核心采用 MIT，ABC/BSAT 见 [许可清单](../../THIRD_PARTY_NOTICES.md)。完整集成只依赖本地 CPU 和本地编译器。

```powershell
$baseDB = (Resolve-Path '../../../tcjap-replay').Path
python build.py $baseDB joint interval holes trigger
python provenance.py $baseDB | Set-Content -Encoding utf8 .local/repeat-builds.json
```

若检出目录不按示例并排放置，直接将 $baseDB 设为实际绝对路径。构建初始三组的历史脚本见 3705fbc；它们的正式二进制未在加入触发器后重编。all-builds.json 记录本次所有实际构建的 SHA-256、编译器与 1141 个共用链接对象的组合指纹。新构建的 PE 文件包含链接器元数据，复跑以新实测二进制指纹独立记账。

## 新建一轮配对与诊断

按以下顺序运行，在可见全部试验进程的 Windows 宿主环境执行。每个调用等待空闲物理核。对照和候选使用相同物理核和逻辑处理器，子进程亲和性回读写入结果目录。监视器检查同核及兄弟逻辑核上的外部求解器、定核 Python 任务；观察不到的普通 OS 调度和跨核共享资源负载仍存在。每个标签应使用全新名称以保留前次输出。超时计满 30 秒，同时保存实际外部墙钟。另行采集的带跟踪运行上限 120 秒，仅用于正确性和分项诊断。

```powershell
python admit.py three repeat-three
python admit.py profile repeat-profile
python admit.py trace repeat-trace
python admit.py four repeat-four
python admit.py trigger-profile repeat-trigger-profile
python admit.py trigger-trace repeat-trigger-trace
python check_trigger.py --base-profile repeat-profile --base-trace repeat-trace --trigger-profile repeat-trigger-profile --trigger-trace repeat-trigger-trace
python admit.py holdout repeat-holdout
python admit.py confirm-audit repeat-confirm-audit
python validate_confirmation.py repeat-holdout repeat-confirm-audit --build-manifest .local/repeat-builds.json --dest .local/repeat-summary
```

results 每次启动保存 manifest.json；每次求解保存 request、launch、result 与原始 solver.log 或无损 gzip，guard.jsonl 给出采样时间、物理核与竞争进程。complete.json 对应整个同函数的完整块。第一个被污染的批次有 EXCLUDED.md，后续中断或启动前遇竞争的目录保留 controller.log；所有这些目录都排除于正式分母。
