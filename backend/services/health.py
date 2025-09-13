# backend/health.py
"""
Health score utilities.

Factors (0..100) → weighted sum (0..100).
Windows:
- Logins & API trend: 30d
- Feature adoption & support load: 90d
- Invoice timeliness: last few invoices

Weights reflect SaaS retention drivers.
"""

from typing import Dict

WEIGHTS: Dict[str, float] = {
    "loginFrequency":     0.25,
    "featureAdoption":    0.25,
    "supportLoad":        0.15,
    "invoiceTimeliness":  0.20,
    "apiTrend":           0.15,
}

TOTAL_KEY_FEATURES: int = 5

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

def _pct(x: float) -> float:
    return _clamp01(x) * 100.0

def score_login_frequency(logins_30d: int, target: int = 12) -> float:
    """
    Map last-30d logins to 0..100. A target of ~12 (3/week) yields realistic centering.
    """
    return _pct(min(1.0, logins_30d / max(1, target)))

def score_feature_adoption(distinct_features_used_90d: int, total_features: int = TOTAL_KEY_FEATURES) -> float:
    if total_features <= 0:
        return 50.0
    return _pct(distinct_features_used_90d / float(total_features))

def score_support_load(tickets_90d: int, max_tickets: int = 10) -> float:
    x = 1.0 - min(1.0, tickets_90d / max_tickets)
    return _pct(x)

def score_invoice_timeliness_counts(on_time_invoices: int, total_invoices: int, neutral_if_no_history: bool = True) -> float:
    if total_invoices <= 0:
        return 50.0 if neutral_if_no_history else 0.0
    return _pct(on_time_invoices / float(total_invoices))

def score_api_trend(curr_30d: int, prev_30d: int, smoothing: int = 3) -> float:
    num = curr_30d + smoothing
    den = max(1, prev_30d + smoothing)
    ratio = num / den
    return round(50.0 + 50.0 * (ratio - 1.0) / (ratio + 1.0), 2)

def weighted_score(factors_0_100: Dict[str, float]) -> float:
    total = 0.0
    for name, w in WEIGHTS.items():
        total += w * factors_0_100.get(name, 0.0)
    return round(total, 2)
