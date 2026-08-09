import json
from pathlib import Path


PORTFOLIO = Path("outputs/data/portfolio.json")


def load():
    assert PORTFOLIO.exists(), "Run the pipeline before output-contract tests"
    return json.loads(PORTFOLIO.read_text(encoding="utf-8"))


def test_portfolio_contract_and_client_coverage():
    portfolio = load()
    assert portfolio["summary"]["clients"] == 20
    assert portfolio["summary"]["opportunities"] == 100
    assert len(portfolio["clients"]) == 20
    assert all(len(client["monthly"]) == 5 for client in portfolio["clients"])


def test_every_number_has_coherent_uncertainty_and_provenance():
    portfolio = load()
    for item in portfolio["opportunities"]:
        for field in ("current_share", "total_wallet_zar", "revenue_gap_zar"):
            values = item[field]
            assert values["p10"] <= values["p50"] <= values["p90"]
        assert item["observed_activity_zar"] <= item["total_wallet_zar"]["p10"] + 1e-6
        assert item["provenance"]["observed_activity_zar"] in {"observed", "accounting-derived"}


def test_three_or_more_grounded_briefs_are_available():
    brief_files = list(Path("outputs/briefs").glob("*.md"))
    assert len(brief_files) >= 3
    for path in brief_files[:3]:
        text = path.read_text(encoding="utf-8")
        assert "## Evidence and confidence" in text
        assert "## Next action" in text
        assert "## Evidence and confidence" in text


def test_showcase_public_facts_are_cited_and_anchors_are_active():
    portfolio = load()
    evidence = portfolio["public_evidence"]
    assert evidence["anchor_impact"]["audited_public_facts"] == 31
    assert evidence["anchor_impact"]["active_product_anchors"] == 15
    assert evidence["anchor_impact"]["showcase_clients"] == ["E01", "E02", "E09"]
    assert all(fact["audit_status"] == "audited" for fact in evidence["facts"])
    assert all(fact["page"] and fact["available_date"] and fact["source_url"] for fact in evidence["facts"])
    assert evidence["anchor_impact"]["median_relative_interval_width_reduction"] > 0.50
    assert evidence["anchor_impact"]["median_confidence_lift"] > 0.20
    for entity_id in ("E01", "E02", "E09"):
        client = next(item for item in portfolio["clients"] if item["entity_id"] == entity_id)
        assert client["evidence_summary"]["active_public_anchors"] == 5
        assert client["debt_maturity_anchor"]["audit_status"] == "audited"


def test_rate_and_prior_sensitivity_is_explicit():
    sensitivity = load()["sensitivity"]
    assert sensitivity["scenario_count"] == 9
    assert len(sensitivity["scenarios"]) == 9
    assert {scenario["prior_case"] for scenario in sensitivity["scenarios"]} == {"low", "base", "high"}
    assert {scenario["rate_case"] for scenario in sensitivity["scenarios"]} == {"low", "base", "high"}
    assert all(scenario["top_product"] == "Trade finance" for scenario in sensitivity["scenarios"])
    assert all(scenario["trade_finance_top10_count"] == 2 for scenario in sensitivity["scenarios"])
    assert sensitivity["trade_finance_dominant_scenarios"] == 0


def test_showcase_briefs_include_page_linked_public_anchor_citations():
    for entity_id in ("E01", "E02", "E09"):
        text = Path(f"outputs/briefs/{entity_id}.md").read_text(encoding="utf-8")
        assert "### Public anchor citations" in text
        assert "p." in text
        assert "public from" in text
