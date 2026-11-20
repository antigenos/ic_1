# Source attribution

This reconstruction builds the DATE 2026 exact-synthesis plugin by Marcel Walter, Michael Feldmeier and Robert Wille, the pinned ABC fork, and the local relation evaluator released by the TCJAP Project9 contributors. The build compiles these sources from checksum-verified upstream archives. The integration patches, reason auditor, witness checks and run records identify the work performed in this repository.

| Upstream material | Notice carried here | Source |
|---|---|---|
| ABC host and its object inventory | [Regents of the University of California notice](licenses/ABC-copyright.txt) | [allen1236/abc at c851fce](https://github.com/allen1236/abc/tree/c851fce40d9dde1aaf32b087a0f449751ea070dc) |
| MiniSat-derived BSAT search loop | [Original solver source notice](licenses/BSAT-MiniSat-notice.txt) | [satSolver.c](https://github.com/allen1236/abc/blob/c851fce40d9dde1aaf32b087a0f449751ea070dc/src/sat/bsat/satSolver.c) |
| Chair for Design Automation, TUM, pexact | [Upstream MIT license](licenses/pexact-MIT.md) | [cda-tum/ext-pexact at 7253861](https://github.com/cda-tum/ext-pexact/tree/7253861c224e7c9de2c802e61c86f89338253544) |
| Project9 local relation evaluator and its public checker | [Upstream MIT license](licenses/TCJAP-MIT.txt) | [qmkkk/TCJAP at 59e5a0e](https://github.com/qmkkk/TCJAP/tree/59e5a0e954d6a0a6711b2bdc9898db875ede6889) |

The published local kernel and its provenance are described in the [upstream release manifest](https://github.com/qmkkk/TCJAP/blob/59e5a0e954d6a0a6711b2bdc9898db875ede6889/CORE_PROVENANCE.json). Each downloaded archive retains its original notices and license files, including those for components within ABC.
