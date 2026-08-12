from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import minimize

from .contracts import ProductNeedEstimate


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0)))


def _published_probability(value: float) -> float:
    """Publish PU estimates at a portable, decision-sufficient precision.

    L-BFGS-B termination can differ by a few 1e-8 across SciPy/BLAS builds.
    Six decimals is well beyond the UI/policy precision and prevents those
    solver implementation details from changing committed products.
    """

    return round(float(value), 6)


@dataclass(frozen=True)
class PURecord:
    opportunity_id: str
    entity_id: str
    product: str
    features: tuple[float, ...]
    labelled_positive: bool


class PositiveUnlabelledNeedModel:
    """Transparent Elkan-Noto estimator under the SCAR assumption."""

    def fit_predict(self, records: Sequence[PURecord]) -> list[ProductNeedEstimate]:
        if not records:
            return []
        matrix = np.asarray([record.features for record in records], dtype=float)
        labels = np.asarray(
            [record.labelled_positive for record in records], dtype=float
        )
        if labels.sum() < 2 or labels.sum() >= len(labels):
            raise ValueError(
                "PU fitting requires at least two labelled positives and two unlabelled cases"
            )
        means = matrix.mean(axis=0)
        scales = matrix.std(axis=0)
        scales[scales < 1e-9] = 1.0
        design = np.column_stack([np.ones(len(matrix)), (matrix - means) / scales])

        def objective(beta: np.ndarray) -> float:
            probabilities = _sigmoid(design @ beta)
            likelihood = -np.sum(
                labels * np.log(probabilities + 1e-12)
                + (1 - labels) * np.log(1 - probabilities + 1e-12)
            )
            return float(likelihood + 0.5 * np.sum(beta[1:] ** 2))

        result = minimize(objective, np.zeros(design.shape[1]), method="L-BFGS-B")
        selection_probabilities = _sigmoid(design @ result.x)
        selection_constant = _published_probability(
            np.clip(selection_probabilities[labels == 1].mean(), 0.15, 1.0)
        )
        needs = np.clip(selection_probabilities / selection_constant, 0.0, 1.0)
        return [
            ProductNeedEstimate(
                opportunity_id=record.opportunity_id,
                entity_id=record.entity_id,
                product=record.product,
                positive_label_observed=record.labelled_positive,
                labelled_positive_probability=_published_probability(
                    selection_probabilities[index]
                ),
                product_need_probability=_published_probability(needs[index]),
                selection_constant=selection_constant,
                assumptions=[
                    "selected positives are correct",
                    "SCAR: positive labelling is conditionally independent of features",
                    "unlabelled cases may contain latent positives",
                    "representative fixture results do not establish bank-population calibration",
                ],
            )
            for index, record in enumerate(records)
        ]
