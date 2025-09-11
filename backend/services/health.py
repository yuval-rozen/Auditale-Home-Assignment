from __future__ import annotations
from typing import Dict

# weights can be tuned later, but keep them documented
WEIGHTS = {
    "loginFrequency": 0.25,
    "featureAdoption": 0.25,
    "supportLoad":    0.20,
    "invoiceTimeliness": 0.20,
    "apiTrend":       0.10,
}

TOTAL_KEY_FEATURES = 5  # assume 5 “important” features for normalization

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def score_login_frequency(logins_30d: int, target: int = 20) -> float:
    # 20 logins / 30 days = 100
    return clamp01(logins_30d / float(target)) * 100.0

def score_feature_adoption(distinct_features_used: int, total_features: int = TOTAL_KEY_FEATURES) -> float:
    if total_features <= 0: return 0.0
    return clamp01(distinct_features_used / float(total_features)) * 100.0

def score_support_load(tickets_90d: int, max_tickets: int = 10) -> float:
    # fewer tickets = better score
    if max_tickets <= 0: return 100.0
    return clamp01(1.0 - (tickets_90d / float(max_tickets))) * 100.0

def score_invoice_timeliness(on_time_ratio: float) -> float:
    # ratio already 0..1
    return clamp01(on_time_ratio) * 100.0

def score_api_trend(curr_calls_30d: int, prev_calls_30d: int) -> float:
    # trend: -100% .. +infinity. map to 0..100 with 50 as neutral
    if prev_calls_30d <= 0 and curr_calls_30d <= 0:
        return 50.0
    if prev_calls_30d <= 0:
        return 100.0  # from zero to something, very positive
    change = (curr_calls_30d - prev_calls_30d) / float(prev_calls_30d)
    # map: -100% -> 0, 0% -> 50, +100% -> 100, cap beyond
    if change <= -1.0: return 0.0
    if change >= 1.0:  return 100.0
    return (change + 1.0) * 50.0

def weighted_score(factors_0_100: Dict[str, float]) -> float:
    total = 0.0
    for k, w in WEIGHTS.items():
        total += w * factors_0_100.get(k, 0.0)
    return round(total, 2)
