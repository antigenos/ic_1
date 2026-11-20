# Exact synthesis with optimal switching activity

This branch reconstructs the DATE 2026 experiment and the later TCJAP algorithm using the public artifacts. The pinned plugin and ABC fork come from the [TCJAP authors' source notice](https://github.com/qmkkk/TCJAP/blob/59e5a0e954d6a0a6711b2bdc9898db875ede6889/THIRD_PARTY_NOTICES.md). The public TCJAP core omits the integrated SAT solver. Any new integration here requires its own correctness checks and timing evidence.

## Initial research record

1. Scope and assets. Recover the exact truth table under the original two-input gate library and minimize activity of the internal gates. Measure time to finish that task. Freeze public inputs in `sources.json`.
2. Source. [Walter, Feldmeier and Wille, DATE 2026](https://doi.org/10.23919/DATE69613.2026.11539139), [author PDF](https://www.cda.cit.tum.de/files/eda/2026_date_exact_synthesis_with_optimal_switching_activity.pdf). Section V explicitly identifies runtime. Section IV-C reports 211 of 222 classes within a three-day cutoff. The TCJAP comparison uses 208 full-support functions and 300 seconds per class. Preserve both protocols.
3. Implementation. In the pinned plugin, `init.cpp::RunPexact` maps mode 0 to queue search, 1 to free search, and 2 to binary search with step 75. The truth table for the four-input Figure 7 example must be passed as `0189`. A leading 0 matters to the parser.
4. Algorithm map. Section II defines the activity of a signal over N truth rows. For a rows with value one, its contribution is 2a(N−a). `pexact.c::PexaManGetAct` sums that value over internal gates, omitting the fixed output. `PexaManMarkup` assigns SAT variables for operations and predecessors. `PexaManEval` simulates the candidate. `PexaManAddPClausesBdd` and `PexaManAddCardinalityBdd` encode count constraints. Section III-D Algorithms 1, 2 and 3 enter at lines 2786, 3034 and 3176 of `pexact.c`. The binary mode's inner search starts at line 3128. Independent verification must recompute the printed circuit, including the complemented output, and distinguish witness validity from minimality.
5. Residual problem for this reproduction. TCJAP already reports improvements to this task. Its public artifact provides local support calculations and aggregate results, but the complete solver, explanations, per-instance logs and construction history are private. An independently checkable reconstruction against the pinned baseline remains necessary. This admits baseline reproduction and diagnosis. No new research novelty is asserted.

**Stage 6 acceptance.** Build and identify the executable, time separate author calls and replay each returned gate on every truth-table row. Check the DATE Figure 7 reference S=304 on 0189 and inspect any difference before interpreting timings. Record a solver's optimality claim separately from any independently established lower bound.

## Build and exercise the pinned baseline

Run `python tools/prepare.py` from this repository (Python 3.12+). On Linux with the ABC build dependencies, run `make -C .local/abc -j8`. On Windows, use MSYS2 UCRT64 GCC/G++, MSYS GNU make 4.4.1 and `make -C .local/abc -f ../../tools/windows.mk -j12 abc.exe` with the UCRT64 and MSYS bin directories on PATH. Keep the toolchain and options fixed for all comparisons.

The Windows build uses the standard-width integer interface, a gnu11 C dialect, and MinGW libraries. `giaMan.c` includes `math.h` inside a function. Pre-including that header for this translation unit allows the MinGW inline definitions at file scope. The host build does not change the author's synthesis code.

For the first witness, run `python tools/run_case.py .local/abc/abc.exe 96 evidence/baseline-xor3 --inputs 3 --mode 0 --seconds 30`. The three-input parity circuit has an internal two-input XOR and a free output XOR. Then use `python tools/run_case.py .local/abc/abc.exe 0189 evidence/baseline-0189 --mode 2 --seconds 300`. On Linux use the executable without the .exe suffix. Each run directory is exclusive to one invocation.
