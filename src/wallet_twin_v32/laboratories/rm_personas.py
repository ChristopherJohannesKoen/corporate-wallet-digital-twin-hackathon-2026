"""RM persona simulator: five personas, eight tasks, zero adoption evidence.

This exercises the workbench against realistic usage patterns — an RM who
prepares thoroughly, one who checks a single number between meetings, one who
distrusts the model and probes its evidence. It surfaces which surfaces get
used, which get ignored, and where a task takes more steps than it should.

**Every session sets ``real_participant=False``, and that is the point.** The
SCALE_READY gate requires at least five *real* supervised sessions per RM. If
fixture sessions could count toward it, a simulation would promote the system
to production readiness — the exact substitution the promotion twin exists to
prevent. The flag is not a label on the data; it is what makes these sessions
structurally incapable of satisfying the gate, asserted by test in both
directions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Sequence, Tuple

import numpy as np

RM_PERSONA_LAB_VERSION = "v32-rm-persona-simulator-1.0.0"

#: Set on every simulated session. Never configurable: a parameter that could
#: be flipped to True would be a parameter that eventually is.
REAL_PARTICIPANT = False


@dataclass(frozen=True)
class Persona:
    """An RM archetype, described by how they actually work."""

    persona_id: str
    title: str
    description: str
    #: Probability of opening the evidence trail behind a number.
    evidence_scrutiny: float
    #: Probability of abandoning a task that takes too many steps.
    impatience: float
    #: Baseline steps this persona takes before acting.
    deliberation: int


PERSONAS: Tuple[Persona, ...] = (
    Persona(
        "thorough-preparer",
        "Thorough preparer",
        "Reviews the full evidence trail the evening before a client meeting.",
        evidence_scrutiny=0.85,
        impatience=0.10,
        deliberation=6,
    ),
    Persona(
        "between-meetings",
        "Between meetings",
        "Checks one number in ninety seconds, on a phone, in a corridor.",
        evidence_scrutiny=0.15,
        impatience=0.70,
        deliberation=2,
    ),
    Persona(
        "sceptic",
        "Sceptic",
        "Distrusts model output and probes for the assumption that breaks it.",
        evidence_scrutiny=0.95,
        impatience=0.25,
        deliberation=8,
    ),
    Persona(
        "portfolio-planner",
        "Portfolio planner",
        "Works across the whole book rather than one client at a time.",
        evidence_scrutiny=0.55,
        impatience=0.20,
        deliberation=7,
    ),
    Persona(
        "new-joiner",
        "New joiner",
        "Learning the product set; relies on the twin to tell them what to ask.",
        evidence_scrutiny=0.45,
        impatience=0.35,
        deliberation=5,
    ),
)


@dataclass(frozen=True)
class Task:
    """Something an RM is actually trying to do."""

    task_id: str
    title: str
    #: Minimum interactions if everything goes well.
    optimal_steps: int
    #: Whether the task requires reading evidence to complete correctly.
    requires_evidence: bool


TASKS: Tuple[Task, ...] = (
    Task("find-top-opportunity", "Find the top opportunity for one client", 3, False),
    Task("explain-a-number", "Explain where a wallet estimate came from", 4, True),
    Task("check-evidence-tier", "Check whether a cell is anchored or prior-led", 2, True),
    Task("prepare-conversation", "Prepare for a specific client conversation", 6, True),
    Task("compare-two-clients", "Compare two clients in the same sector", 5, False),
    Task("find-pending-evidence", "See what approval is blocking a stronger estimate", 3, True),
    Task("review-portfolio", "Review the whole portfolio for the week", 7, False),
    Task("challenge-a-recommendation", "Challenge a recommendation and see the basis", 5, True),
)


@dataclass
class Session:
    """One persona attempting one task."""

    session_id: str
    persona_id: str
    task_id: str
    started_at: datetime
    steps_taken: int
    completed: bool
    opened_evidence: bool
    abandoned: bool
    #: Always False. Present on every record so a consumer cannot mistake this
    #: for a real supervised session.
    real_participant: bool = field(default=REAL_PARTICIPANT, init=False)

    def as_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.session_id,
            "persona_id": self.persona_id,
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "steps_taken": self.steps_taken,
            "completed": self.completed,
            "opened_evidence": self.opened_evidence,
            "abandoned": self.abandoned,
            "real_participant": self.real_participant,
        }


def simulate_sessions(
    *,
    as_of: date,
    personas: Sequence[Persona] = PERSONAS,
    tasks: Sequence[Task] = TASKS,
    repetitions: int = 3,
    seed: int = 20260630,
) -> List[Session]:
    """Every persona attempts every task, repeated for a usable sample."""
    rng = np.random.default_rng(seed)
    started = datetime.combine(as_of, datetime.min.time())
    sessions: List[Session] = []

    for repetition in range(repetitions):
        for persona in personas:
            for task in tasks:
                # Steps scale with deliberation but are floored at the optimum:
                # nobody completes a task in fewer steps than it takes.
                overhead = rng.poisson(persona.deliberation / 3.0)
                steps = task.optimal_steps + int(overhead)
                abandoned = bool(
                    rng.random() < persona.impatience * (steps / max(task.optimal_steps, 1) - 1.0)
                )
                opened_evidence = bool(rng.random() < persona.evidence_scrutiny)
                # A task needing evidence is not completed correctly without it.
                completed = (not abandoned) and (opened_evidence or not task.requires_evidence)
                sessions.append(
                    Session(
                        session_id=f"{persona.persona_id}:{task.task_id}:{repetition}",
                        persona_id=persona.persona_id,
                        task_id=task.task_id,
                        started_at=started + timedelta(minutes=len(sessions) * 7),
                        steps_taken=steps,
                        completed=completed,
                        opened_evidence=opened_evidence,
                        abandoned=abandoned,
                    )
                )
    return sessions


def persona_report(sessions: Sequence[Session]) -> Dict[str, object]:
    """Where the workbench helps and where it does not.

    Reports friction as well as success. A simulator that only counted
    completions would say the interface works everywhere, which is never true
    and would make the exercise pointless.
    """
    by_persona: Dict[str, Dict[str, object]] = {}
    for persona in PERSONAS:
        subset = [item for item in sessions if item.persona_id == persona.persona_id]
        by_persona[persona.persona_id] = {
            "title": persona.title,
            "sessions": len(subset),
            "completion_rate": round(
                sum(1 for item in subset if item.completed) / max(len(subset), 1), 4
            ),
            "abandonment_rate": round(
                sum(1 for item in subset if item.abandoned) / max(len(subset), 1), 4
            ),
            "evidence_open_rate": round(
                sum(1 for item in subset if item.opened_evidence) / max(len(subset), 1), 4
            ),
            "mean_steps": round(
                float(np.mean([item.steps_taken for item in subset])) if subset else 0.0, 4
            ),
        }

    by_task: Dict[str, Dict[str, object]] = {}
    for task in TASKS:
        subset = [item for item in sessions if item.task_id == task.task_id]
        mean_steps = float(np.mean([item.steps_taken for item in subset])) if subset else 0.0
        by_task[task.task_id] = {
            "title": task.title,
            "optimal_steps": task.optimal_steps,
            "mean_steps": round(mean_steps, 4),
            "step_overhead": round(mean_steps - task.optimal_steps, 4),
            "completion_rate": round(
                sum(1 for item in subset if item.completed) / max(len(subset), 1), 4
            ),
            "requires_evidence": task.requires_evidence,
        }

    worst = max(by_task.items(), key=lambda pair: pair[1]["step_overhead"])
    return {
        "lab_version": RM_PERSONA_LAB_VERSION,
        "personas": len(PERSONAS),
        "tasks": len(TASKS),
        "sessions": len(sessions),
        "real_participant_sessions": 0,
        "by_persona": by_persona,
        "by_task": by_task,
        "highest_friction_task": {"task_id": worst[0], **worst[1]},
        "adoption_gate_effect": {
            "counts_toward_supervised_pilot_gate": False,
            "reason": (
                "Every session carries real_participant=False. The "
                "supervised-pilot-completed gate requires five real supervised "
                "sessions per RM; a simulation that could satisfy it would let "
                "fixture data promote the system to production readiness."
            ),
        },
        "bank_meaning": (
            "This measures the interface against plausible usage. It is not "
            "adoption evidence and no count here appears in any adoption metric."
        ),
    }


def real_sessions(sessions: Sequence[Session]) -> List[Session]:
    """Sessions that may count toward the adoption gate. Always empty here.

    Exists so the adoption path is written once and exercised by the fixture,
    rather than being untested code that first runs against real RMs.
    """
    return [item for item in sessions if item.real_participant]


__all__ = [
    "PERSONAS",
    "REAL_PARTICIPANT",
    "RM_PERSONA_LAB_VERSION",
    "TASKS",
    "Persona",
    "Session",
    "Task",
    "persona_report",
    "real_sessions",
    "simulate_sessions",
]
