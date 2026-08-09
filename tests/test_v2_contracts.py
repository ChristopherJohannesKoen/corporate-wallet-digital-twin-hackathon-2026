from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from wallet_twin_v2.bounds import BoundEvidence, DeterministicBoundsEngine
from wallet_twin_v2.contracts import ClaimClass, IntervalEstimate, Money


def test_interval_contract_rejects_incoherent_quantiles():
    with pytest.raises(ValidationError):
        IntervalEstimate(
            lower=10,
            median=5,
            upper=20,
            nominal_coverage=0.9,
            model_version="test",
            as_of=date(2026, 6, 30),
            claim_class=ClaimClass.POSTERIOR,
        )


def test_contracts_forbid_unknown_fields():
    with pytest.raises(ValidationError):
        Money(
            amount=Decimal("1"),
            normalized_amount=Decimal("1"),
            currency="ZAR",
            normalized_currency="ZAR",
            unexpected="not allowed",
        )


def test_bounds_are_independent_and_never_below_observed():
    result = DeterministicBoundsEngine().calculate(
        100.0,
        date(2026, 6, 30),
        BoundEvidence(lower=80, upper=500, capacity=450),
    )
    assert result.claim_class == ClaimClass.IDENTIFIED_BOUND
    assert result.lower == 100
    assert result.upper == 450
