# FinGuard AI

## AI-Powered Financial Fraud & Anomaly Intelligence Platform

FinGuard AI is a hackathon-ready fraud operations prototype that turns synthetic transaction activity into explainable, human-reviewed risk decisions.

> Prototype — Demonstration using synthetic financial transaction data. Not connected to real banking systems.

## Problem statement

Fraud teams need to recognize unusual activity quickly, understand why it was flagged, and retain accountable human control over high-impact decisions. Conventional dashboards often show a score without the evidence or investigation context required to act confidently.

## Our solution

FinGuard combines machine-learning anomaly detection with an AI investigation layer and explicit human approval. It surfaces transaction-level evidence, assigns a 0–100 risk score, recommends the correct operating action, and records decisions in an audit trail.

## Key features

- Isolation Forest anomaly detection on programmatically generated synthetic transactions
- Explainable risk scores, behavioral factors, and risk levels
- Executive KPIs, risk distribution, anomaly rate, and transaction value by risk level
- Fraud Alert Center with live filters, search, and sorting
- Qwen AI investigation via OpenRouter and deterministic local fallback
- Human-in-the-loop approval, audit events, and synthetic transaction simulator
- Responsive enterprise fintech/cybersecurity dashboard

## Architecture

```text
Synthetic transaction simulator → preprocessing → scikit-learn Isolation Forest
→ explainable risk score + factors → Qwen AI investigation or local fallback
→ recommended action + human review → React operations dashboard + audit trail
```

## ML approach

The backend uses scikit-learn `IsolationForest` with transformed synthetic features: amount, account age, velocity, international flag, transaction hour, and merchant risk. The normalized anomaly signal contributes to the 0–100 FinGuard risk score; concrete factors make that score explainable.

## Qwen AI role

Machine learning identifies anomalous activity. Qwen performs the investigation/reasoning step, returning a structured executive summary, evidence, possible scenario, and confidence from the selected synthetic transaction context. Qwen never approves transactions. Configure server-side integration in `backend/.env`:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=qwen/<model-slug>
```

If either setting is absent or OpenRouter fails, FinGuard uses a deterministic local fallback based on the same transaction’s actual risk data. API keys never reach React.

## Human-in-the-loop controls

| Risk level | Required action | Human review |
| --- | --- | --- |
| CRITICAL | HOLD & VERIFY | Required |
| HIGH | MANUAL REVIEW | Required |
| MEDIUM | MONITOR | Not required |
| LOW | ALLOW | Not required |

## Technology stack

- Python, FastAPI, Pydantic, HTTPX
- scikit-learn and NumPy
- React, TypeScript, Vite, Lucide
- OpenRouter OpenAI-compatible API with Qwen

## API architecture

- `GET /health`, `GET /api/health`, `GET /api/dashboard`
- `GET /api/transactions`, `GET /api/transactions/{transaction_id}`
- `GET /api/alerts`, `GET /api/risk-summary`, `GET /api/top-risk`
- `GET /api/audit-trail?transaction_id=...`
- `POST /api/investigate`, `POST /api/simulate`
- `POST /api/transactions/{transaction_id}/approval`

## How to run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend
npm install
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --port 5174
```

## Demo flow

1. Open the Overview and show live ML KPIs and risk distribution.
2. Select a CRITICAL alert in the Fraud Alert Center.
3. Show the risk meter and actual contributing factors.
4. Choose **Investigate with Qwen AI** for the structured investigation.
5. Highlight `HOLD & VERIFY` and `HUMAN REVIEW REQUIRED`.
6. Record a decision and show the updated audit trail.
7. Select **Simulate Transaction** to evaluate a new synthetic event.

## Future scope

- Persistent audit storage, role-based access, and case management
- Streaming ingestion for approved anonymized sources
- Model monitoring, feedback loops, and configurable policies
