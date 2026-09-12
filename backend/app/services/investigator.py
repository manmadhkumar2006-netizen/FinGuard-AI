class QwenInvestigator:
    """Compact local narrative used by the initial dashboard seed data.

    Full OpenRouter/Qwen investigations are performed on demand by ``ai.qwen_agent``.
    """

    async def investigate(self, transaction: dict, factors: list[str], risk_score: int) -> str:
        return self._demo_summary(transaction, factors, risk_score)

    @staticmethod
    def _demo_summary(transaction: dict, factors: list[str], risk_score: int) -> str:
        if risk_score >= 80:
            return f"Critical deviation from this account's simulated baseline: {', '.join(factors[:3]).lower()}. Pause and require analyst verification before release."
        if risk_score >= 60:
            return f"Multiple atypical signals require review: {', '.join(factors[:2]).lower()}. Request step-up verification and monitor the account."
        return "Pattern is within the simulated behavioral range. Continue passive monitoring."
