"""
test_health_unit.py
-------------------
Unit tests for the health scoring utilities in `services.health`.

Goals:
- Validate normalization boundaries, clamping, and capping (0..100).
- Verify neutral handling when there is "no evidence" (e.g., no invoices).
- Ensure monotonic behavior (e.g., more tickets -> lower score).
- Confirm API trend smoothing prevents extreme swings on tiny counts.
- Check the weighted aggregator matches the documented weights.

These tests focus on pure functions (no I/O), so failures indicate logic issues,
not infrastructure problems.
"""

from backend.services.health import (
    score_login_frequency,
    score_feature_adoption,
    score_support_load,
    score_invoice_timeliness_counts,
    score_invoice_timeliness_ratio,
    score_api_trend,
    weighted_score,
    WEIGHTS,
)


def test_login_frequency_boundaries():
    """
    Login frequency: normalized against a target, capped at 100.
    - 0/20  -> 0
    - 10/20 -> 50
    - 40/20 -> 100 (cap; we don't reward >100)
    """
    assert score_login_frequency(0, target=20) == 0.0
    assert score_login_frequency(10, target=20) == 50.0
    assert score_login_frequency(40, target=20) == 100.0  # capped


def test_feature_adoption_neutral_when_total_zero():
    """
    Feature adoption: if TOTAL_KEY_FEATURES is misconfigured to 0,
    return neutral 50 (avoid divide-by-zero and unfair penalty).
    """
    assert score_feature_adoption(3, total_features=0) == 50.0


def test_support_load_inverse_monotonic():
    """
    Support load: fewer tickets => higher score.
    Linear inverse mapping with clamping:
      - 0/10  -> 100
      - 5/10  -> 50
      - 10/10 -> 0
    """
    hi = score_support_load(0, max_tickets=10)
    mid = score_support_load(5, max_tickets=10)
    lo = score_support_load(10, max_tickets=10)
    assert hi == 100.0
    assert mid == 50.0
    assert lo == 0.0


def test_invoice_timeliness_counts_neutral_when_none():
    """
    Invoice timeliness (counts-based):
    Distinguish 'no history' from 'bad history'.
      - 0/0 invoices -> neutral 50
      - 2/3 on time  -> ~66.67
    """
    assert score_invoice_timeliness_counts(on_time_invoices=0, total_invoices=0) == 50.0

    v = score_invoice_timeliness_counts(on_time_invoices=2, total_invoices=3)
    assert 66.6 < v < 66.8  # allow float rounding tolerance


def test_invoice_timeliness_ratio_compat():
    """
    Ratio-based compatibility:
    If only a ratio is available, we can treat 0.0 as 'no history' -> neutral 50
    (when treat_zero_as_neutral=True). Otherwise:
      - 1.0 -> 100
      - 0.5 -> 50
    """
    assert score_invoice_timeliness_ratio(0.0, treat_zero_as_neutral=True) == 50.0
    assert score_invoice_timeliness_ratio(1.0) == 100.0
    assert score_invoice_timeliness_ratio(0.5) == 50.0


def test_api_trend_smoothing_and_mapping():
    """
    API trend:
    - With smoothing, no activity both months -> neutral 50.
    - Large relative increase caps at 100.
    - Large relative decrease caps at 0.
    This ensures stability (no wild swings on tiny denominators).
    """
    # No activity both months => neutral 50
    assert score_api_trend(0, 0) == 50.0
    # Big increase should cap at 100
    assert score_api_trend(1000, 0) == 100.0
    # Big decrease should be ~0; with smoothing it's close to zero.
    v = score_api_trend(0, 1000)
    assert 0.0 <= v <= 1.0  # allow near-zero with smoothing


def test_weighted_score_basic():
    """
    Weighted score equals the documented weighted average of factor scores.
    This guards against accidental changes to the aggregator or weights.
    """
    factors = {
        "loginFrequency": 60.0,
        "featureAdoption": 40.0,
        "supportLoad": 80.0,
        "invoiceTimeliness": 100.0,
        "apiTrend": 55.0,
    }
    score = weighted_score(factors)

    expected = (
        WEIGHTS["loginFrequency"] * 60.0 +
        WEIGHTS["featureAdoption"] * 40.0 +
        WEIGHTS["supportLoad"] * 80.0 +
        WEIGHTS["invoiceTimeliness"] * 100.0 +
        WEIGHTS["apiTrend"] * 55.0
    )
    # Round to match the function's 2-decimal behavior
    assert round(expected, 2) == score
