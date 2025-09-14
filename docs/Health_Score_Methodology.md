# Customer Health Score Methodology

## Overview

The **Customer Health Score** is a composite metric (0–100) that represents the overall engagement, satisfaction, and retention risk of a customer in a SaaS environment. 
It is designed to provide Customer Success teams with an early-warning signal of at-risk accounts and a clear view of healthy, engaged customers.
A higher score (closer to 100) indicates strong engagement and low churn risk, while lower scores highlight accounts that may require proactive intervention. 
- Healthy: 70–100
- At-risk: 50–69
- Churn-risk: <50
This methodology links operational activity data (logins, API usage, feature adoption), 
customer experience data (support tickets), and financial reliability (invoice timeliness) into a single interpretable framework.

---

## Data Model

### Segments and Personas

The synthetic dataset (`seed.py`) generates **realistic and correlated customer behaviors** across three main **segments**:  
- **Enterprise** – large organizations, higher baseline activity, more support load.  
- **SMB (Small/Medium Businesses)** – moderate usage, balanced activity.  
- **Startup** – fast-moving, lightweight activity, potentially volatile.  

Each segment contains **personas** representing three states of customer health:  
- **Healthy** – engaged, timely payers, broad feature usage.  
- **At-Risk** – declining engagement or mixed signals.  
- **Churn-Risk** – low usage, poor adoption, frequent support issues, or late payments.  

The personas control baseline distributions for logins, API calls, features used, support tickets, and invoice payment behavior.

### Correlated Behaviors

The dataset explicitly models correlations found in real SaaS systems:  
- **More logins ↔ more API calls** – engaged users interact both via UI and API.  
- **Healthy customers use more features** – breadth of feature adoption correlates with stickiness.  
- **Enterprise customers file more support tickets** – reflecting larger deployments.  
- **Late payments cluster in churn-risk personas** – financial reliability mirrors engagement.  

The dataset includes **90 days of events** and **four billing cycles** per customer, ensuring enough historical data to calculate robust health scores.

---

## Scoring Factors

The health score is composed of five factors, each measured over a defined time window and scaled to a 0–100 range using formulas in `health.py`.

### 1. Login Frequency
- **Meaning:** How often users from the account log into the SaaS product (proxy for engagement).  
- **Measurement:** Count of login events in the last 30 days.  
- **Formula:**  
  score = min(1, logins_30d / target) × 100  
  Default target = 12 logins (≈3 per week).  
- **Why Important:** Consistent logins are the strongest predictor of engagement. Accounts falling below expected login cadence often precede churn.

### 2. Feature Adoption
- **Meaning:** Breadth of product features adopted by the customer.  
- **Measurement:** Distinct features used in the last 90 days (out of TOTAL_KEY_FEATURES = 5).  
- **Formula:**  
  score = (distinct features / total features) × 100  
- **Why Important:** Customers using a wider set of features are more embedded in the product ecosystem and harder to displace.

### 3. Support Load
- **Meaning:** Number of support tickets raised, indicating friction or dissatisfaction.  
- **Measurement:** Count of tickets in the last 90 days.  
- **Formula:**  
  score = (1 – min(1, tickets_90d / maxTickets)) × 100  
  With maxTickets = 10.  
- **Why Important:** High support demand signals product challenges, customer frustration, or costly support overhead.

### 4. Invoice Timeliness
- **Meaning:** Reliability of customer payments.  
- **Measurement:** Ratio of invoices paid on or before due date.  
- **Formula:**  
  score = (on-time invoices / total invoices) × 100  
  (Default neutral = 50 if no invoices exist.)  
- **Why Important:** Timely payments are a strong proxy for satisfaction and financial health. Late payers often correlate with disengagement.

### 5. API Trend
- **Meaning:** Direction of API usage (growing, stable, or declining).  
- **Measurement:** Compare API calls in current 30 days vs. previous 30 days.  
- **Formula:**  
  ratio = (curr_30d + s) / (prev_30d + s), s=3  
  score = 50 + 50 × (ratio – 1) / (ratio + 1)  
- **Why Important:** Positive usage trends indicate deepening adoption; negative trends can foreshadow disengagement.

---

## Weighting

The five factors are combined with weights reflecting their relative importance in SaaS retention:

| Factor              | Weight |
|---------------------|--------|
| Login Frequency     | 0.25   |
| Feature Adoption    | 0.25   |
| Invoice Timeliness  | 0.20   |
| Support Load        | 0.15   |
| API Trend           | 0.15   |

Rationale:  
- **Logins + Adoption (50%)**: Core engagement.  
- **Invoice Timeliness (20%)**: Financial health is a leading retention driver.  
- **Support Load & API Trend (30%)**: Secondary signals that refine prediction.  

---

## Final Score

The **weighted score** is calculated as:  

Health Score = Σ (weight_f × score_f)

Where weight_f is the weight for factor f.  

**Interpretation:**  
- **70–100:** Healthy, growing account.  
- **50–69:** At-Risk – proactive intervention required.
- **0–49:** Churn Risk – urgent attention needed.
- 
---

## Examples

1. **Healthy Enterprise Customer**  
   - Logins: 20 in last 30d → ~100  
   - Features: 4/5 → 80  
   - Tickets: 2 in 90d → 80  
   - Invoices: 3/3 on time → 100  
   - API Trend: slight growth → 55  
   **Score ≈ 88** → Healthy.

2. **At-Risk Startup**  
   - Logins: 6 in last 30d → 50  
   - Features: 1/5 → 20  
   - Tickets: 4 in 90d → 60  
   - Invoices: 2/3 on time → 66  
   - API Trend: flat → 50  
   **Score ≈ 50** → At-Risk.

3. **Churn-Risk SMB**  
   - Logins: 0 in last 30d → 0  
   - Features: 0/5 → 0  
   - Tickets: 8 in 90d → 20  
   - Invoices: 1/4 on time → 25  
   - API Trend: strong decline → 30  
   **Score ≈ 18** → Churn Risk.

---

## Limitations and Future Improvements

### Current Simplifications
- **Synthetic Data:** Personas are statistically generated; real-world datasets may show more nuanced patterns.  
- **Static Weights:** Factor weights are fixed and based on heuristics, not empirical modeling.  
- **Limited Factors:** Only operational and billing data are considered; customer sentiment, NPS, contract value, and renewal stage are excluded.  

### Future Enhancements
- **Machine Learning Calibration:** Learn weights dynamically from historical churn/retention data.  
- **Segmentation-Aware Scoring:** Different weights per segment (enterprise vs startup).  
- **Additional Inputs:** Include product telemetry depth, renewal contract info, and survey feedback.  
- **Temporal Smoothing:** Apply rolling averages to reduce volatility.  

---

## Conclusion

This methodology provides a **clear, interpretable, and actionable health score** framework. While simplified for synthetic data, it captures the key SaaS retention drivers and can be extended with empirical tuning for production environments.
