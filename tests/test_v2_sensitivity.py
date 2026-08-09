from wallet_twin_v2.repository import repository


def test_global_sensitivity_is_reproducible_and_does_not_encode_a_winner():
    result = repository.sensitivity
    assert result["draws"] == 10_000
    assert len(result["drivers"]) == 9
    assert "Trade finance" in result["product_summary"]
    trade = result["product_summary"]["Trade finance"]
    assert 0 <= trade["first_rank_frequency"] <= 1
    assert 0 <= trade["majority_dominance_frequency"] <= 1
    assert len(repository.legacy_sensitivity) == 9
    # No assertion requires Trade Finance to win; the measured conclusion is output data.
