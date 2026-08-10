from __future__ import annotations

import math
from typing import Any, Sequence


def build_treasury_graph(
    entity_id: str,
    entity_name: str,
    sector: str,
    relationship_breadth: int,
    countries: Sequence[dict[str, Any]],
    mean_shadow_entropy: float,
) -> dict[str, Any]:
    """Build a transparent representative topology from the Syn Bank fixture.

    GLEIF is registered as a future identity/parent sensor, but no legal-entity
    match is fabricated in this offline fixture.
    """
    values = [
        max(0.0, float(country.get("value_zar", 0.0))) for country in countries[:5]
    ]
    total = sum(values) or 1.0
    weights = [value / total for value in values]
    concentration = sum(weight * weight for weight in weights)
    diversity = 1.0 - concentration
    breadth_component = min(1.0, relationship_breadth / 5.0)
    corridor_component = min(1.0, math.log1p(len(countries)) / math.log(6.0))
    complexity = 100.0 * (
        0.30 * breadth_component
        + 0.30 * corridor_component
        + 0.25 * diversity
        + 0.15 * mean_shadow_entropy
    )
    nodes = [
        {
            "node_id": entity_id,
            "label": entity_name,
            "node_type": "corporate",
            "sector": sector,
        }
    ]
    edges = []
    for index, (country, weight) in enumerate(zip(countries[:5], weights)):
        node_id = f"corridor:{entity_id}:{index}"
        nodes.append(
            {
                "node_id": node_id,
                "label": country.get("name", "Unknown"),
                "node_type": "trade_corridor",
            }
        )
        edges.append(
            {
                "source": entity_id,
                "target": node_id,
                "weight": weight,
                "claim_class": "OBSERVED",
                "provenance": "SYNTHETIC_SIMULATION",
            }
        )
    return {
        "entity_id": entity_id,
        "nodes": nodes,
        "edges": edges,
        "treasury_complexity_index": round(complexity, 2),
        "components": {
            "relationship_breadth": round(breadth_component, 4),
            "corridor_diversity": round(diversity, 4),
            "shadow_network_entropy": round(mean_shadow_entropy, 4),
        },
        "gleif_resolution_status": "REGISTERED_SENSOR_NOT_ENTITY_RESOLVED",
        "measurement_status": "SYN_BANK_SIMULATION_TOPOLOGY_NOT_ACTUAL_CLIENT_TREASURY_GRAPH",
    }
