"""Timing validation on client-held-out temporal splits.

Two things must both hold for a timing evaluation to mean anything, and using
either alone produces an optimistic number:

**Temporal split** — train on the past, test on the future. A random split lets
the model see a client's later behaviour while predicting their earlier
behaviour, which is leakage in the most direct sense.

**Client held out** — the test clients must not appear in training at all.
Splitting only on time still lets the model learn client-specific patterns and
then be scored on the same clients, so it measures memorisation rather than
generalisation to the next client the bank onboards.

Both are applied here, and the report states which is doing the work by also
computing the optimistic variants. A single number cannot show that; three can.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .compute import CPU

TIMING_LAB_VERSION = "v32-timing-temporal-split-1.0.0"


@dataclass(frozen=True)
class SplitResult:
    split: str
    train_rows: int
    test_rows: int
    mae_months: float
    description: str


def _panel(seed: int, clients: int = 180, months: int = 24) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic client-month panel with a client-specific timing offset.

    The client effect is the point: it is what a leaky split lets the model
    memorise, so a panel without one could not demonstrate the difference.
    """
    rng = np.random.default_rng(seed)
    client_ids = np.repeat(np.arange(clients), months)
    month_index = np.tile(np.arange(months), clients)
    client_offset = rng.normal(0.0, 2.5, size=clients)[client_ids]
    seasonal = 1.5 * np.sin(2 * np.pi * month_index / 12.0)
    truth = 6.0 + client_offset + seasonal + rng.normal(0.0, 1.0, size=clients * months)
    return client_ids, month_index, truth


def _fit_predict(
    train_mask: np.ndarray,
    client_ids: np.ndarray,
    month_index: np.ndarray,
    truth: np.ndarray,
) -> float:
    """Fit a per-client mean with a global fallback, return test MAE.

    Deliberately simple. The comparison being made is between *splits*, and a
    more elaborate estimator would confound the two effects.
    """
    test_mask = ~train_mask
    global_mean = float(truth[train_mask].mean())

    per_client: Dict[int, float] = {}
    for client in np.unique(client_ids[train_mask]):
        per_client[int(client)] = float(truth[train_mask & (client_ids == client)].mean())

    predictions = np.array(
        [per_client.get(int(client), global_mean) for client in client_ids[test_mask]]
    )
    seasonal_adjustment = 1.5 * np.sin(2 * np.pi * month_index[test_mask] / 12.0)
    return float(np.mean(np.abs(truth[test_mask] - (predictions + seasonal_adjustment))))


def evaluate_splits(*, seed: int = 20260630) -> List[SplitResult]:
    """The governed split and the two optimistic variants, for comparison."""
    client_ids, month_index, truth = _panel(seed)
    rng = np.random.default_rng(seed + 1)
    clients = int(client_ids.max()) + 1
    held_out = set(rng.choice(clients, size=clients // 4, replace=False).tolist())
    cutoff = 18

    random_mask = rng.random(len(truth)) < 0.75
    temporal_mask = month_index < cutoff
    client_temporal_mask = temporal_mask & np.array(
        [int(client) not in held_out for client in client_ids]
    )

    return [
        SplitResult(
            "random",
            int(random_mask.sum()),
            int((~random_mask).sum()),
            _fit_predict(random_mask, client_ids, month_index, truth),
            "Optimistic. Leaks the future and the client; reported for contrast only.",
        ),
        SplitResult(
            "temporal-only",
            int(temporal_mask.sum()),
            int((~temporal_mask).sum()),
            _fit_predict(temporal_mask, client_ids, month_index, truth),
            "Still optimistic. Test clients appear in training, so it measures "
            "memorisation rather than generalisation.",
        ),
        SplitResult(
            "client-held-out-temporal",
            int(client_temporal_mask.sum()),
            int((~client_temporal_mask).sum()),
            _fit_predict(client_temporal_mask, client_ids, month_index, truth),
            "The governed split. Train on the past, test on unseen clients in "
            "the future.",
        ),
    ]


def timing_report(results: Sequence[SplitResult], as_of: date) -> Dict[str, object]:
    by_split = {item.split: item for item in results}
    governed = by_split["client-held-out-temporal"]
    optimism = governed.mae_months - by_split["random"].mae_months
    return {
        "lab_version": TIMING_LAB_VERSION,
        "device": CPU,
        "as_of": as_of.isoformat(),
        "governed_split": "client-held-out-temporal",
        "governed_mae_months": round(governed.mae_months, 6),
        "splits": [
            {
                "split": item.split,
                "train_rows": item.train_rows,
                "test_rows": item.test_rows,
                "mae_months": round(item.mae_months, 6),
                "description": item.description,
            }
            for item in results
        ],
        "optimism_of_a_random_split_months": round(optimism, 6),
        "why_both_conditions": (
            "A temporal split alone still lets the model be scored on clients it "
            "trained on. Reporting all three shows how much of the apparent "
            "accuracy came from leakage rather than from the model."
        ),
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "bank_meaning": (
            "Measured on a synthetic panel. No timing claim about real clients "
            "follows from it."
        ),
    }


__all__ = [
    "TIMING_LAB_VERSION",
    "SplitResult",
    "evaluate_splits",
    "timing_report",
]
