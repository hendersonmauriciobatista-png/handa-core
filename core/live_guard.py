import os


class LiveGuard:
    """
    Trava explícita para execução LIVE REAL.
    """

    @staticmethod
    def is_live_real_allowed() -> bool:
        """
        Retorna True apenas se TODAS as condições forem atendidas.
        """
        enable_flag = os.getenv("ENABLE_LIVE_REAL", "false").lower() == "true"
        confirm_flag = os.getenv("CONFIRM_LIVE_REAL", "").upper() == "YES"
        return enable_flag and confirm_flag

    @classmethod
    def require_live_real(cls) -> None:
        if not cls.is_live_real_allowed():
            raise RuntimeError(cls.reason_blocked())

    @staticmethod
    def reason_blocked() -> str:
        return (
            "LIVE REAL BLOQUEADO — condições não atendidas. "
            "Exija ENABLE_LIVE_REAL=true e CONFIRM_LIVE_REAL=YES."
        )
