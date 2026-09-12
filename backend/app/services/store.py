from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
from typing import Optional
from app.models.schemas import ReviewStatus, Transaction
from app.services.detector import AnomalyDetector
from app.services.investigator import QwenInvestigator
from ai.qwen_agent import risk_level


MERCHANTS = [("Northstar Market", "Retail", "US", .15), ("CloudForge", "Software", "US", .20), ("MetroLink", "Transport", "IN", .16), ("Vertex Electronics", "Electronics", "SG", .58), ("Global Luxe", "Luxury", "AE", .79), ("Night Owl Digital", "Digital Goods", "NG", .88)]
PAYMENTS = ["Virtual card", "Debit card", "Bank transfer", "Mobile wallet"]
DEVICES = ["Known iPhone", "Known Android", "New desktop browser", "Unrecognized mobile device"]


class DemoStore:
    def __init__(self) -> None:
        self.transactions: dict[str, Transaction] = {}
        self.audit_log: list[dict] = []

    async def seed(self, count: int = 80) -> None:
        rng = random.Random(12)
        now = datetime.now(timezone.utc)
        rows = []
        for index in range(count):
            merchant, category, country, merchant_risk = rng.choice(MERCHANTS)
            suspicious = index < 13
            amount = round(rng.lognormvariate(7.7 if suspicious else 4.4, .75 if suspicious else .62), 2)
            rows.append({
                "id": f"TXN-{2026091200 + index}", "timestamp": now - timedelta(minutes=index * 19),
                "customer_id": f"CUST-{41000 + (index % 27)}",
                "merchant": merchant, "category": category, "country": country, "amount": amount,
                "payment_method": rng.choice(PAYMENTS), "account_age_days": rng.randint(2, 25) if suspicious else rng.randint(50, 1600),
                "device": rng.choice(DEVICES[2:]) if suspicious else rng.choice(DEVICES[:2]),
                "historical_average": round(rng.uniform(35, 160) if suspicious else rng.uniform(25, 125), 2),
                "velocity_24h": rng.randint(5, 12) if suspicious else rng.randint(0, 4),
                "is_international": suspicious and rng.random() < .72, "hour": rng.randint(0, 4) if suspicious else rng.randint(6, 23),
                "merchant_risk": merchant_risk,
            })
        detector = AnomalyDetector()
        results = detector.score(rows)
        investigator = QwenInvestigator()
        for row, result in zip(rows, results):
            status = ReviewStatus.PENDING if result.risk_score >= 65 else ReviewStatus.CLEAR
            action = "Hold & require analyst approval" if result.risk_score >= 80 else "Step-up verification" if result.risk_score >= 60 else "Continue monitoring"
            investigation = await investigator.investigate(row, result.factors, result.risk_score)
            self.transactions[row["id"]] = Transaction(
                **{key: value for key, value in row.items() if key not in {"hour", "merchant_risk"}},
                anomaly_score=result.anomaly_score, risk_score=result.risk_score, risk_factors=result.factors,
                recommended_action=action, review_status=status, investigation=investigation,
            )
            self.record_audit(row["id"], "Transaction detected", "Synthetic transaction ingested and evaluated.", row["timestamp"])
            self.record_audit(row["id"], "ML anomaly identified", "Isolation Forest anomaly score: %.3f." % result.anomaly_score, row["timestamp"])
            self.record_audit(row["id"], "Risk score generated", "Risk score: %s/100 (%s)." % (result.risk_score, risk_level(result.risk_score)), row["timestamp"])

    def list_transactions(self, risk: Optional[str] = None) -> list[Transaction]:
        values = sorted(self.transactions.values(), key=lambda item: item.timestamp, reverse=True)
        if risk == "flagged": return [item for item in values if item.risk_score >= 60]
        if risk == "critical": return [item for item in values if item.risk_score >= 80]
        return values

    def stats(self) -> dict:
        values = list(self.transactions.values())
        return {
            "total_transactions": len(values),
            "flagged_transactions": sum(item.risk_score >= 60 for item in values),
            "critical_transactions": sum(item.risk_score >= 80 for item in values),
            "amount_monitored": round(sum(item.amount for item in values), 2),
            "risk_trend": [32, 41, 28, 47, 38, 57, 43, 61, 52, 68, 46, 59],
        }

    def risk_summary(self) -> dict:
        levels = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        values = list(self.transactions.values())
        distribution = {level: sum(risk_level(item.risk_score) == level for item in values) for level in levels}
        transaction_value_by_risk = {level: round(sum(item.amount for item in values if risk_level(item.risk_score) == level), 2) for level in levels}
        return {
            "distribution": distribution,
            "transaction_value_by_risk": transaction_value_by_risk,
            "anomaly_rate": round(100 * sum(item.risk_score >= 60 for item in values) / max(len(values), 1), 1),
            "human_reviews_required": sum(item.review_status == ReviewStatus.PENDING and item.risk_score >= 60 for item in values),
        }

    def alerts(self) -> list[dict]:
        return [{
            "transaction_id": item.id, "customer_id": item.customer_id, "amount": item.amount,
            "merchant": item.merchant, "location": item.country, "risk_score": item.risk_score,
            "risk_level": risk_level(item.risk_score), "risk_reasons": item.risk_factors,
            "recommended_action": item.recommended_action, "timestamp": item.timestamp,
        } for item in sorted(self.transactions.values(), key=lambda item: (item.risk_score, item.amount), reverse=True) if item.risk_score >= 40]

    def record_audit(self, transaction_id: str, event: str, detail: str, timestamp: Optional[datetime] = None) -> dict:
        entry = {"id": "AUD-%05d" % (len(self.audit_log) + 1), "timestamp": timestamp or datetime.now(timezone.utc), "transaction_id": transaction_id, "event": event, "detail": detail}
        self.audit_log.append(entry)
        return entry

    def audits(self, transaction_id: Optional[str] = None) -> list[dict]:
        values = [event for event in self.audit_log if not transaction_id or event["transaction_id"] == transaction_id]
        return sorted(values, key=lambda event: event["timestamp"], reverse=True)

    def approve(self, tx_id: str, status: ReviewStatus, analyst: str, note: str) -> Optional[Transaction]:
        transaction = self.transactions.get(tx_id)
        if not transaction: return None
        transaction.review_status = status
        self.record_audit(tx_id, "Decision recorded", "%s marked transaction as %s. %s" % (analyst, status.value, note))
        return transaction

    async def simulate(self) -> Transaction:
        """Generate one new synthetic transaction and evaluate it with the existing ML detector."""
        rng = random.Random(len(self.transactions) + 99)
        merchant, category, country, merchant_risk = rng.choice(MERCHANTS)
        suspicious = rng.random() < .35
        now = datetime.now(timezone.utc)
        row = {
            "id": "SIM-%s" % (len(self.transactions) + 1), "customer_id": "SIM-CUST-%03d" % rng.randint(1, 999),
            "timestamp": now, "merchant": merchant, "category": category, "country": country,
            "amount": round(rng.lognormvariate(7.4 if suspicious else 4.4, .7 if suspicious else .55), 2),
            "payment_method": rng.choice(PAYMENTS), "device": rng.choice(DEVICES[2:] if suspicious else DEVICES[:2]),
            "historical_average": round(rng.uniform(35, 150) if suspicious else rng.uniform(25, 125), 2),
            "account_age_days": rng.randint(2, 25) if suspicious else rng.randint(60, 1300),
            "velocity_24h": rng.randint(5, 12) if suspicious else rng.randint(0, 4),
            "is_international": suspicious and rng.random() < .7, "hour": rng.randint(0, 4) if suspicious else rng.randint(7, 22), "merchant_risk": merchant_risk,
        }
        baseline = [{"amount": item.amount, "account_age_days": item.account_age_days, "velocity_24h": item.velocity_24h, "is_international": item.is_international, "hour": item.timestamp.hour, "merchant_risk": .5} for item in self.transactions.values()]
        result = AnomalyDetector().score(baseline + [row])[-1]
        status = ReviewStatus.PENDING if result.risk_score >= 65 else ReviewStatus.CLEAR
        action = "Hold & require analyst approval" if result.risk_score >= 80 else "Step-up verification" if result.risk_score >= 60 else "Continue monitoring"
        item = Transaction(**{key: value for key, value in row.items() if key not in {"hour", "merchant_risk"}}, anomaly_score=result.anomaly_score, risk_score=result.risk_score, risk_factors=result.factors, recommended_action=action, review_status=status, investigation=await QwenInvestigator().investigate(row, result.factors, result.risk_score))
        self.transactions[item.id] = item
        self.record_audit(item.id, "Simulation transaction detected", "Synthetic simulation evaluated by Isolation Forest.")
        self.record_audit(item.id, "Risk score generated", "Risk score: %s/100 (%s)." % (item.risk_score, risk_level(item.risk_score)))
        return item


store = DemoStore()
