from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import Alert, ApprovalRequest, ApprovalResult, AuditEvent, DashboardStats, InvestigationRequest, InvestigationResult, RiskSummary, ReviewStatus, SimulationResult, Transaction
from app.services.store import store
from ai.qwen_agent import QwenInvestigationAgent


@asynccontextmanager
async def lifespan(_: FastAPI):
    await store.seed()
    yield


app = FastAPI(title="FinGuard AI API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # Permit local Vite dev ports while keeping browser access restricted to loopback hosts.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "data_policy": "synthetic-demo-only"}


@app.get("/api/health")
async def api_health():
    return await health()


@app.get("/api/dashboard", response_model=DashboardStats)
async def dashboard():
    return store.stats()


@app.get("/api/transactions", response_model=list[Transaction])
async def transactions(risk: Optional[str] = Query(default=None, pattern="^(flagged|critical)?$")):
    return store.list_transactions(risk)


@app.get("/api/alerts", response_model=list[Alert])
async def alerts():
    return store.alerts()


@app.get("/api/risk-summary", response_model=RiskSummary)
async def risk_summary():
    return store.risk_summary()


@app.get("/api/top-risk", response_model=list[Transaction])
async def top_risk():
    return sorted(store.transactions.values(), key=lambda item: (item.risk_score, item.amount), reverse=True)[:8]


@app.get("/api/audit-trail", response_model=list[AuditEvent])
async def audit_trail(transaction_id: Optional[str] = None):
    return store.audits(transaction_id)


@app.get("/api/transactions/{transaction_id}", response_model=Transaction)
async def transaction(transaction_id: str):
    item = store.transactions.get(transaction_id)
    if not item: raise HTTPException(status_code=404, detail="Transaction not found")
    return item


@app.post("/api/investigate", response_model=InvestigationResult)
async def investigate(request: InvestigationRequest):
    item = store.transactions.get(request.transaction_id)
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found")
    result = await QwenInvestigationAgent().investigate(item)
    store.record_audit(item.id, "AI investigation generated", "Provider: %s. Action: %s." % (result["ai_provider"], result["recommended_action"]))
    return result


@app.post("/api/simulate", response_model=SimulationResult)
async def simulate():
    item = await store.simulate()
    return {"transaction": item, "alert_created": item.risk_score >= 40}


@app.post("/api/transactions/{transaction_id}/approval", response_model=ApprovalResult)
async def approval(transaction_id: str, request: ApprovalRequest):
    if request.decision not in {ReviewStatus.APPROVED, ReviewStatus.ESCALATED}:
        raise HTTPException(status_code=422, detail="Decision must be approved or escalated")
    item = store.approve(transaction_id, request.decision, request.analyst, request.note)
    if not item: raise HTTPException(status_code=404, detail="Transaction not found")
    return ApprovalResult(transaction=item, audit_event=store.audit_log[-1]["detail"])
