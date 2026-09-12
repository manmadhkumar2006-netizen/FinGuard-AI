"""OpenRouter-backed Qwen investigation with a deterministic, transaction-driven fallback."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx

from app.core.config import settings


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def risk_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def review_policy(score: int) -> Dict[str, Any]:
    level = risk_level(score)
    policy = {
        "CRITICAL": ("HOLD & VERIFY", True),
        "HIGH": ("MANUAL REVIEW", True),
        "MEDIUM": ("MONITOR", False),
        "LOW": ("ALLOW", False),
    }
    action, human_review_required = policy[level]
    return {"risk_level": level, "recommended_action": action, "human_review_required": human_review_required}


def transaction_context(transaction: Any) -> Dict[str, Any]:
    amount_ratio = round(transaction.amount / max(transaction.historical_average, 0.01), 2)
    return {
        "transaction_id": transaction.id,
        "risk_score": transaction.risk_score,
        "risk_level": risk_level(transaction.risk_score),
        "reasons": transaction.risk_factors,
        "amount": transaction.amount,
        "historical_average": transaction.historical_average,
        "amount_ratio": amount_ratio,
        "time": transaction.timestamp.isoformat(),
        "device": transaction.device,
        "location": transaction.country,
        "merchant": transaction.merchant,
        "category": transaction.category,
        "payment_method": transaction.payment_method,
        "velocity_24h": transaction.velocity_24h,
        "is_international": transaction.is_international,
        "account_age_days": transaction.account_age_days,
    }


class QwenInvestigationAgent:
    async def investigate(self, transaction: Any) -> Dict[str, Any]:
        context = transaction_context(transaction)
        policy = review_policy(transaction.risk_score)
        if not settings.openrouter_api_key or not settings.openrouter_model:
            return self._fallback(context, policy)
        try:
            payload = await self._request_qwen(context)
            return self._from_ai_payload(context, policy, payload)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            return self._fallback(context, policy)

    async def _request_qwen(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "You are FinGuard AI, a financial-fraud investigation assistant. Analyze ONLY this synthetic "
            "transaction context. Return valid JSON only with keys: summary, suspicious_factors (array of strings), "
            "possible_fraud_scenario, confidence (integer 0-100). Do not invent facts beyond the context.\n\n"
            + json.dumps(context, default=str)
        )
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                OPENROUTER_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": "Bearer " + settings.openrouter_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed.get("suspicious_factors"), list):
            raise ValueError("AI response did not contain investigation factors")
        return parsed

    @staticmethod
    def _from_ai_payload(context: Dict[str, Any], policy: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "transaction_id": context["transaction_id"],
            "risk_score": context["risk_score"],
            **policy,
            "summary": str(payload["summary"]),
            "suspicious_factors": [str(item) for item in payload["suspicious_factors"]],
            "possible_fraud_scenario": str(payload["possible_fraud_scenario"]),
            "confidence": max(0, min(100, int(payload.get("confidence", context["risk_score"]))),),
            "ai_provider": "openrouter:" + settings.openrouter_model,
        }

    @staticmethod
    def _fallback(context: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
        factors: List[str] = list(context["reasons"])
        if context["amount_ratio"] >= 2:
            factors.append("Amount is %.1fx the historical average" % context["amount_ratio"])
        if "Unrecognized" in context["device"] or "New " in context["device"]:
            factors.append("Transaction originated from " + context["device"].lower())
        if context["is_international"]:
            factors.append("Cross-border transaction location: " + context["location"])
        factors = list(dict.fromkeys(factors))
        scenario = (
            "Potential account takeover or unauthorized card use" if policy["human_review_required"]
            else "No dominant fraud pattern; retain this transaction for behavioral monitoring"
        )
        summary = (
            "%s risk (%s/100): %s." % (
                policy["risk_level"].title(), context["risk_score"],
                "; ".join(factors[:3]) if factors else "no material anomaly reasons recorded",
            )
        )
        return {
            "transaction_id": context["transaction_id"],
            "risk_score": context["risk_score"],
            **policy,
            "summary": summary,
            "suspicious_factors": factors,
            "possible_fraud_scenario": scenario,
            "confidence": min(96, max(55, context["risk_score"] + (5 if factors else 0))),
            "ai_provider": "local_fallback",
        }
