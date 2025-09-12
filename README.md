### Sample Data
- Seeded once via `python db/seed.py --customers 80 --seed 42`
- Deterministic: using a fixed seed ensures the same dataset on every machine
- Idempotent: script checks if customers already exist and exits to avoid duplicates
- Content:
    - 80 customers across segments (enterprise, SMB, startup)
    - ~90 days of events (login, api_call), feature usage, support tickets
    - 3 monthly invoices with on-time and late payments

### Health Score Methodology
The Customer Health Score is designed to capture early signals of engagement, satisfaction, and risk. It combines multiple usage and financial factors into a single, weighted score from 0–100, which we bucket into:
- Healthy: 75–100
- At-risk: 50–74
- Churn-risk: <50
- This provides an at-a-glance view of customer stability and allows teams to proactively intervene before churn occurs.

Factors and Measurement
1. Login Frequency (25%)
- Why it matters: Consistent logins indicate customers are actively engaging with the product. Sudden drops in logins are strong predictors of churn.
- How measured: Count of logins in the last 30 days, normalized against a target of 20 logins (≈ daily activity).
- Why 30 days: A short-term window highlights recent engagement, not legacy activity.

2. Feature Adoption Rate (25%)
- Why it matters: Customers who adopt multiple “key features” become more “sticky,” as they rely on more parts of the product. Low adoption suggests limited perceived value.
- How measured: Distinct features used in the last 90 days ÷ total key features (5 in this model).
- Why 90 days: Feature adoption unfolds over weeks/months, not days.

3. Support Ticket Volume (20%)
- Why it matters: Excessive tickets suggest friction or dissatisfaction, even if customers are engaged. Fewer tickets generally imply smoother experience.
- How measured: Inverse of ticket count over the last 90 days (fewer tickets → higher score).
- Why 90 days: A quarter-long window smooths out random spikes in activity.

4. Invoice Payment Timeliness (20%)
- Why it matters: Late or missed payments are strong financial churn signals, even if usage is high.
- How measured: % of invoices paid on or before the due date in the last 3 billing cycles.
- Special case: If no billing history exists yet, we treat the score as neutral (50), not 0. This avoids unfairly penalizing new customers with no invoices.
- Why this approach: No history ≠ bad history. Only actual late payments should drag scores down.

5. API Usage Trends (10%)
- Why it matters: For integrated customers, stable or increasing API calls show deeper reliance on the platform. A decline signals disengagement.
- How measured: Compare API calls in the last 30 days vs. the previous 30.
Growth → >50
Decline → <50
No change → 50
- Why 30 days: API activity can shift quickly when integrations break or workloads change.

Weighting Rationale
Engagement (login frequency) and adoption (feature breadth) are weighted highest (25% each) because they are the strongest predictors of retention.
Support load and billing reliability matter strongly but are secondary signals (20% each).
API usage trends are weighted lowest (10%) because not all segments (e.g., SMBs) rely on APIs, but when present, it’s a valuable indicator.
