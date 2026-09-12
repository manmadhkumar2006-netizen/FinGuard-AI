from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    CLEAR = "cleared"
    PENDING = "pending_review"
    APPROVED = "approved"
    ESCALATED = "escalated"


class Transaction(BaseModel):
    id: str
    customer_id: str
    timestamp: datetime
    merchant: str
    category: str
    country: str
    amount: float
    payment_method: str
    device: str
    historical_average: float
    account_age_days: int
    velocity_24h: int
    is_international: bool
    risk_score: int = Field(ge=0, le=100)
    anomaly_score: float
    risk_factors: list[str]
    recommended_action: str
    review_status: ReviewStatus
    investigation: str


class ApprovalRequest(BaseModel):
    decision: ReviewStatus
    analyst: str = Field(min_length=2, max_length=80)
    note: str = Field(default="", max_length=500)


class DashboardStats(BaseModel):
    total_transactions: int
    flagged_transactions: int
    critical_transactions: int
    amount_monitored: float
    risk_trend: list[int]


class ApprovalResult(BaseModel):
    transaction: Transaction
    audit_event: str


class InvestigationRequest(BaseModel):
    transaction_id: str


class InvestigationResult(BaseModel):
    transaction_id: str
    risk_level: str
    risk_score: int = Field(ge=0, le=100)
    summary: str
    suspicious_factors: list[str]
    possible_fraud_scenario: str
    recommended_action: str
    confidence: int = Field(ge=0, le=100)
    human_review_required: bool
    ai_provider: str


class RiskSummary(BaseModel):
    distribution: dict[str, int]
    transaction_value_by_risk: dict[str, float]
    anomaly_rate: float
    human_reviews_required: int


class Alert(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    merchant: str
    location: str
    risk_score: int
    risk_level: str
    risk_reasons: list[str]
    recommended_action: str
    timestamp: datetime


class AuditEvent(BaseModel):
    id: str
    timestamp: datetime
    transaction_id: str
    event: str
    detail: str


class SimulationResult(BaseModel):
    transaction: Transaction
    alert_created: bool
