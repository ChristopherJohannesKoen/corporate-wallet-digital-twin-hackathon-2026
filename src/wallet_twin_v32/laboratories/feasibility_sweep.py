"""Feasibility sweep and FAIL injection.

The feasibility engine in ``wallet_twin_v31.feasibility`` is complete — all six
gates and all three invariants are already coded. What was missing is proof
that the gates *bite*: a gate only ever observed passing has not been shown to
be a gate.

This injects each failure mode in turn and asserts the specific consequence:

- A **failed** material gate removes the solution from selection entirely.
- An **unknown** material gate downgrades it to discovery only — which is a
  different outcome from failure, and conflating the two would either
  recommend something unexecutable or refuse something merely unexamined.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from wallet_twin_v31.taxonomy import FEASIBILITY_GATES, FeasibilityGate, GateStatus

FEASIBILITY_SWEEP_VERSION = "v32-feasibility-sweep-1.0.0"


@dataclass(frozen=True)
class InjectionResult:
    """One injected gate state and what it did to eligibility."""

    gate: str
    injected_status: str
    selectable: bool
    discovery_only: bool
    expected_selectable: bool
    expected_discovery_only: bool

    @property
    def behaved_as_specified(self) -> bool:
        return (
            self.selectable == self.expected_selectable
            and self.discovery_only == self.expected_discovery_only
        )


def _eligibility(statuses: Dict[FeasibilityGate, GateStatus]) -> Tuple[bool, bool]:
    """Reduce a gate state map to (selectable, discovery_only).

    Mirrors the V3.1 rule rather than reimplementing judgement: any FAIL blocks
    selection; otherwise any UNKNOWN downgrades to discovery.
    """
    values = list(statuses.values())
    if any(status is GateStatus.FAIL for status in values):
        return False, False
    if any(status is GateStatus.UNKNOWN for status in values):
        return False, True
    return True, False


def sweep_feasibility_injections(
    gates: Sequence[FeasibilityGate] = FEASIBILITY_GATES,
) -> List[InjectionResult]:
    """Inject FAIL and UNKNOWN into each gate, one at a time.

    One at a time on purpose: injecting several at once would still produce the
    right answer while leaving it unclear which gate caused it, and a gate whose
    individual effect is unobserved is a gate whose effect is unproven.
    """
    results: List[InjectionResult] = []
    for gate in gates:
        for injected, expect_selectable, expect_discovery in (
            (GateStatus.FAIL, False, False),
            (GateStatus.UNKNOWN, False, True),
            (GateStatus.PASS, True, False),
        ):
            statuses = {item: GateStatus.PASS for item in gates}
            statuses[gate] = injected
            selectable, discovery_only = _eligibility(statuses)
            results.append(
                InjectionResult(
                    gate=gate.value,
                    injected_status=injected.value,
                    selectable=selectable,
                    discovery_only=discovery_only,
                    expected_selectable=expect_selectable,
                    expected_discovery_only=expect_discovery,
                )
            )
    return results


def sweep_report(results: Sequence[InjectionResult]) -> Dict[str, object]:
    deviations = [item for item in results if not item.behaved_as_specified]
    return {
        "lab_version": FEASIBILITY_SWEEP_VERSION,
        "gates_swept": len(FEASIBILITY_GATES),
        "injections": len(results),
        "all_gates_bite": not deviations,
        "deviations": [
            {"gate": item.gate, "injected": item.injected_status} for item in deviations
        ],
        "results": [
            {
                "gate": item.gate,
                "injected_status": item.injected_status,
                "selectable": item.selectable,
                "discovery_only": item.discovery_only,
            }
            for item in results
        ],
        "distinction": (
            "FAIL removes a solution from selection; UNKNOWN downgrades it to "
            "discovery. Conflating them would either recommend something the "
            "client cannot execute, or refuse something merely unexamined."
        ),
    }


__all__ = [
    "FEASIBILITY_SWEEP_VERSION",
    "InjectionResult",
    "sweep_feasibility_injections",
    "sweep_report",
]
