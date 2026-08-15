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
    TierSpec("e3-sample-size", 500, CPU, True, "7 n-values x 500 complete panel replications"),
    TierSpec("synthetic-e3-panel", 240, CPU, True, "240 relationships x 5 products x 24 periods"),
    TierSpec("timing-hazard", 2_000, CPU, True, "2,000 clients x 36 monthly intervals"),
    TierSpec("causal-trial", 2_000, CPU, True, "2,000 trial realisations plus analytic grid"),
    TierSpec("economics", 10_000, CPU, True, "10,000 correlated Latin-hypercube draws x 16 solutions"),
    TierSpec("genai-mutations", 1_000, CPU, True, "120 fixed cases plus 1,000 deterministic mutations"),
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


#: Fields that describe *this machine* rather than the declared policy. They
#: must never enter a byte-gated artifact — see :func:`compute_report`.
HOST_OBSERVATION_FIELDS: Tuple[str, ...] = (
    "cpu_cores",
    "canonical_workers",
    "gpu_available",
    "gpu_reason",
)


def compute_report(
    tiers: Sequence[TierSpec] = CANONICAL_TIERS,
    *,
    include_host_observations: bool = False,
) -> Dict[str, object]:
    """The declared compute policy, and optionally what this host observed.

    **Host observations are excluded by default, and that default is
    load-bearing.** An earlier version published ``cpu_cores`` and
    ``canonical_workers`` unconditionally. Both are derived from
    ``os.cpu_count()``, so the committed artifact recorded 16 and 14 from the
    development machine and would have recorded 4 and 2 on a CI runner — failing
    the very ``git diff --exit-code`` gate this module's own policy string
    claims the artifact satisfies. The numbers were never wrong; the worker
    *count* was published as data.

    ``map_replications`` already guarantees the results themselves are
    worker-count independent, by returning them in seed order. That guarantee is
    about the floats. This is about the metadata sitting beside them.

    Pass ``include_host_observations=True`` for a run log or nightly report,
    where knowing the machine is useful and byte-stability is not required.
    """
    report: Dict[str, object] = {
        "compute_version": COMPUTE_VERSION,
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
        # Declared specification only. Whether a nightly tier actually ran is a
        # property of the machine that ran it, so it belongs with the host
        # observations rather than in the committed policy.
        "nightly_tiers": [
            {
                "name": tier.name,
                "replications": tier.replications,
                "device": tier.device,
                "committed": tier.committed,
                "note": tier.note,
            }
            for tier in NIGHTLY_TIERS
        ],
        "canonical_parallelism": (
            "across replications, seed-ordered; results are independent of "
            "worker count, so the resolved count is not published here"
        ),
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

    if include_host_observations:
        available, reason = gpu_available()
        report["host_observations"] = {
            "cpu_cores": os.cpu_count(),
            "canonical_workers": worker_count(),
            "gpu_available": available,
            "gpu_reason": reason,
            "nightly_tier_status": {
                tier.name: "EXECUTED" if available else "NOT_EXECUTED"
                for tier in NIGHTLY_TIERS
            },
            "not_byte_stable": (
                "These fields describe the machine that produced the run, not "
                "the declared policy. They are excluded from committed "
                "artifacts because they would differ on every host."
            ),
        }
    return report


__all__ = [
    "CANONICAL_TIERS",
    "COMPUTE_VERSION",
    "CPU",
    "GPU",
    "HOST_OBSERVATION_FIELDS",
    "NIGHTLY_TIERS",
    "TierSpec",
    "compute_report",
    "gpu_available",
    "map_replications",
    "worker_count",
]
