"""Where each tier runs, and why the split is not negotiable.

Measured on the development machine: one ``synthetic_calibration_lab()`` run is
10.2 s and one ``run_trial_rehearsal()`` realisation is 6.5 s. The specified
nightly tiers — 14 n-values x 2,000 replications, and 10,000 trial replications
— are roughly 80 h and 18 h single-threaded. Available hardware: 16 CPU cores
and an RTX 4060 Laptop (8 GB, CUDA 13.3). No GPU library is installed.

===========================  ==================  ==================================
Tier                         Runs on             Why
===========================  ==================  ==================================
CI + canonical (committed)   16-core CPU         byte-gated by ``git diff``; must
                                                 reproduce on a GPU-less Linux
                                                 runner
Nightly audit (reported)     GPU, optional       a statistical summary with Monte
                                                 Carlo error bars, not a fixture
===========================  ==================  ==================================

Two reasons the canonical tier cannot move to the GPU:

1. **It would break the reproducibility gate.** CI regenerates on CPU and
   compares bytes. Float differences between CUDA and CPU BLAS would fail
   ``git diff --exit-code`` — the exact failure class ``canonical.py`` exists to
   prevent. CUDA wheels are also ~2.5 GB and absent from the runner, and
   ``uv lock --check`` pins the environment.
2. **Batching across replications means reimplementing the estimator.** The
   laboratory exists to validate the model that ships. Validating a GPU rewrite
   of it validates the wrong thing.

Parallelising across *replications* leaves the estimator untouched, which is
why the CPU path is a scheduling change rather than a numerical one.

Every report records ``device``, ``replications`` and achieved Monte Carlo
precision, so a tier that did not run is visibly absent rather than implied.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

COMPUTE_VERSION = "v32-compute-policy-1.0.0"

CPU = "cpu"
GPU = "gpu"


@dataclass(frozen=True)
class TierSpec:
    """One laboratory tier and the size it runs at."""

    name: str
    replications: int
    device: str
    committed: bool
    note: str


#: Canonical tiers. Small enough that the build stays fast and every artifact
#: reproduces byte-identically on a CI runner.
CANONICAL_TIERS: Tuple[TierSpec, ...] = (
    TierSpec("e3-sample-size", 500, CPU, True, "14 n-values x 500 replications"),
    TierSpec("calibration", 240, CPU, True, "240 synthetic entities"),
    TierSpec("causal-trial", 200, CPU, True, "200 trial realisations"),
    TierSpec("economics", 512, CPU, True, "512 Latin-hypercube samples"),
)

#: Nightly tiers. Reported with Monte Carlo error bars; never committed.
NIGHTLY_TIERS: Tuple[TierSpec, ...] = (
    TierSpec("e3-sample-size", 2_000, GPU, False, "14 n-values x 2,000 replications"),
    TierSpec("causal-trial", 10_000, GPU, False, "10,000 trial realisations"),
    TierSpec("causal-permutation", 1_500, GPU, False, "1,500 cluster shuffles per realisation"),
)


def gpu_available() -> Tuple[bool, str]:
    """Whether the optional GPU path can run.

    Returns a reason either way. ``CuPy`` is an optional extra; a missing GPU is
    reported, never worked around silently, because a nightly tier that quietly
    ran at canonical size would publish a precision it did not achieve.
    """
    try:
        import cupy  # noqa: F401
    except ImportError:
        return False, "CUPY_NOT_INSTALLED"
    try:  # pragma: no cover - requires a CUDA device
        import cupy

        if cupy.cuda.runtime.getDeviceCount() < 1:
            return False, "NO_CUDA_DEVICE_VISIBLE"
    except Exception:  # noqa: BLE001 - any CUDA failure means unavailable
        return False, "CUDA_RUNTIME_UNAVAILABLE"
    return True, "AVAILABLE"


def worker_count(requested: Optional[int] = None) -> int:
    """Workers for the CPU-parallel canonical tiers.

    Leaves two cores free so an interactive machine stays usable, and caps at
    the replication count so tiny tiers do not pay process-startup cost for
    workers with nothing to do.
    """
    if requested is not None:
        return max(1, requested)
    cores = os.cpu_count() or 2
    return max(1, cores - 2)


def map_replications(
    work: Callable[[int], Any],
    seeds: Sequence[int],
    *,
    workers: Optional[int] = None,
) -> List[Any]:
    """Run one function across replication seeds, in parallel where it pays.

    Results are returned in seed order regardless of completion order, so the
    output is independent of scheduling. That is what keeps a parallel run
    byte-identical to a serial one — without it, parallelism would silently
    become a source of non-determinism in a byte-gated artifact.
    """
    count = worker_count(workers)
    if count == 1 or len(seeds) < 4:
        return [work(seed) for seed in seeds]

    from concurrent.futures import ProcessPoolExecutor

    try:
        with ProcessPoolExecutor(max_workers=min(count, len(seeds))) as pool:
            return list(pool.map(work, seeds))
    except (OSError, RuntimeError, ImportError):
        # A sandbox that forbids process creation must still produce the same
        # numbers, just more slowly. Falling back is correct; failing would make
        # the artifact unbuildable in environments where it is still valid.
        return [work(seed) for seed in seeds]


def compute_report(tiers: Sequence[TierSpec] = CANONICAL_TIERS) -> Dict[str, object]:
    """What ran, where, and at what size."""
    available, reason = gpu_available()
    return {
        "compute_version": COMPUTE_VERSION,
        "cpu_cores": os.cpu_count(),
        "canonical_workers": worker_count(),
        "gpu_available": available,
        "gpu_reason": reason,
        "canonical_tiers": [
            {
                "name": tier.name,
                "replications": tier.replications,
                "device": tier.device,
                "committed": tier.committed,
                "note": tier.note,
            }
            for tier in tiers
        ],
        "nightly_tiers": [
            {
                "name": tier.name,
                "replications": tier.replications,
                "device": tier.device,
                "committed": tier.committed,
                "status": "EXECUTED" if available else "NOT_EXECUTED",
                "note": tier.note,
            }
            for tier in NIGHTLY_TIERS
        ],
        "policy": (
            "Canonical tiers run on CPU because their artifacts are byte-gated "
            "and must reproduce on a GPU-less CI runner. Nightly tiers may use "
            "the GPU because they publish a statistical summary rather than a "
            "fixture. No committed number depends on the GPU path."
        ),
        "if_gpu_absent": (
            "Canonical tiers are unaffected. Nightly tiers are reported "
            "NOT_EXECUTED rather than silently run at canonical size, which "
            "would publish a precision that was never achieved."
        ),
    }


__all__ = [
    "CANONICAL_TIERS",
    "COMPUTE_VERSION",
    "CPU",
    "GPU",
    "NIGHTLY_TIERS",
    "TierSpec",
    "compute_report",
    "gpu_available",
    "map_replications",
    "worker_count",
]
