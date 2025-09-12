"""
Health score utilities.

This module turns raw usage/finance/support signals into normalized 0..100
factor scores and then into a single weighted health score.

Design goals:
- Simple, explainable math (reviewers can reason about it).
- Stable scores that avoid extreme 0/100 unless the data clearly supports it.
- Neutral handling when there is "no evidence" for a factor (e.g., no invoices yet).

Time windows (chosen for domain reasons, explained in docs):
- Logins and API trend: 30 days (short-term engagement)
- Feature adoption & support load: 90 days (medium-term stability)
- Invoice timeliness: last few invoices (billing cycles), passed in as counts

Weights reflect typical SaaS retention drivers:
- Engagement (login frequency) and adoption (breadth of features) are highest.
- Support pain and billing reliability are important secondary drivers.
- API trend is powerful when present but not used by every customer.
"""

from typing import Dict, Optional


# ------------------------
# Factor weights (0..1 sum)
# ------------------------
WEIGHTS: Dict[str, float] = {
    "loginFrequency":     0.25,  # engagement
    "featureAdoption":    0.25,  # breadth of value
    "supportLoad":        0.20,  # pain/friction
    "invoiceTimeliness":  0.20,  # financial reliability
    "apiTrend":           0.10,  # integration depth / momentum
}

# Number of "key features" your product team cares about for adoption.
# Keep this list in seed/data docs; the model just needs the count.
TOTAL_KEY_FEATURES: int = 5


# ---------------
# Helper utilities
# ---------------
def _clamp01(x: float) -> float:
    """Clamp a float into [0.0, 1.0]."""
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _pct(x: float) -> float:
    """Convert 0..1 to 0..100 with clamping."""
    return _clamp01(x) * 100.0


# -----------------
# Factor score rules
# -----------------
def score_login_frequency(logins_30d: int, target: int = 20) -> float:
    """
    Normalize logins in the last 30 days to 0..100 against a target.

    Rationale:
      - 30 days captures recent engagement.
      - We cap at 100 so abnormally high activity doesn't skew beyond 'excellent'.

    Example:
      logins_30d=10, target=20 --> 50.0
    """
    if target <= 0:
        return 100.0  # degenerate: if there's no target, don't penalize
    return _pct(logins_30d / float(target))


def score_feature_adoption(distinct_features_used_90d: int,
                           total_features: int = TOTAL_KEY_FEATURES) -> float:
    """
    Share of 'key' features the customer actually used in the last 90 days.

    Rationale:
      - Adoption is about breadth (stickiness), not raw counts.
      - 90 days gives a fair window for teams to try multiple features.

    Neutrality:
      - If total_features is 0 (misconfiguration), return neutral 50 to avoid division by zero.
    """
    if total_features <= 0:
        return 50.0  # neutral if no definition of 'key features'
    return _pct(distinct_features_used_90d / float(total_features))


def score_support_load(tickets_90d: int, max_tickets: int = 10) -> float:
    """
    Fewer tickets over 90 days means less friction -> higher score.

    Formula:
      score = 1 - min(tickets_90d / max_tickets, 1)

    Notes:
      - 90 days smooths occasional spikes.
      - If max_tickets <= 0, return 100 (avoid divide-by-zero, don't penalize).
      - This can return 100 when there are 0 tickets; that is intentional.
        If you want to avoid 'free 100s' for completely inactive customers,
        pass an 'activity' hint into your calling code and downweight this factor
        when activity is near zero.
    """
    if max_tickets <= 0:
        return 100.0
    return _pct(1.0 - _clamp01(tickets_90d / float(max_tickets)))


def score_invoice_timeliness_counts(on_time_invoices: int,
                                    total_invoices: int,
                                    neutral_if_no_history: bool = True) -> float:
    """
    % invoices paid on/before due date.

    Neutral handling:
      - If there are ZERO invoices and `neutral_if_no_history` is True,
        return 50. This avoids treating 'no billing yet' as 'all late'.

    Examples:
      on_time=2, total=3 -> 66.67
      on_time=0, total=0 -> 50.0 (neutral if enabled)
    """
    if total_invoices <= 0:
        return 50.0 if neutral_if_no_history else 0.0
    return _pct(on_time_invoices / float(total_invoices))


def score_invoice_timeliness_ratio(on_time_ratio: float,
                                   treat_zero_as_neutral: bool = True) -> float:
    """
    Compatibility helper for existing code that only has a ratio.

    If treat_zero_as_neutral=True, a 0.0 is interpreted as 'no history' and returns 50.
    WARNING: This masks the 'all invoices were late' case. Prefer the *_counts variant
    when you can pass both on_time and total.
    """
    if on_time_ratio <= 0.0 and treat_zero_as_neutral:
        return 50.0
    return _pct(on_time_ratio)


def score_api_trend(curr_calls_30d: int,
                    prev_calls_30d: int,
                    smoothing: int = 5) -> float:
    """
    Map the month-over-month API change into 0..100 with 50 as 'no change'.

    Steps:
      - Compute a smoothed delta: (curr + α - (prev + α)) / (prev + α)
        where α = `smoothing` (pseudo-count) to reduce volatility when counts are small.
      - Then map:
            change <= -100%   ->   0
            change  =   0%    ->  50
            change >= +100%   -> 100
        and linearly in between.

    Examples (with α=5):
      prev=0, curr=0  -> change≈0.0 -> 50.0 (neutral)
      prev=0, curr>0  -> positive but not an automatic 100 (thanks to smoothing)
    """
    denom = float(max(prev_calls_30d + smoothing, 1))
    change = (curr_calls_30d + smoothing - (prev_calls_30d + smoothing)) / denom

    # Hard-cap at [-1, +1] then map to [0, 100] with 50 neutral.
    if change <= -1.0:
        return 0.0
    if change >= 1.0:
        return 100.0
    return (change + 1.0) * 50.0


# -----------------
# Weighted aggregate
# -----------------
def weighted_score(factors_0_100: Dict[str, float]) -> float:
    """
    Combine individual factor scores (each 0..100) into a single 0..100 health score.

    Missing factors default to 0 (conservative). If you prefer 'neutral when missing',
    pass 50s for factors you want to treat as unknown/neutral.

    Example:
      factors = {
        "loginFrequency": 60.0,
        "featureAdoption": 40.0,
        "supportLoad": 80.0,
        "invoiceTimeliness": 100.0,
        "apiTrend": 55.0,
      }
      -> ~67.5 with current weights
    """
    total = 0.0
    for name, weight in WEIGHTS.items():
        total += weight * factors_0_100.get(name, 0.0)
    # Two decimals are nice for UI/readability
    return round(total, 2)
