# controls/confirmations.py

class ConfirmationRequired(Exception):
    """Lançada quando a ação exige confirmação explícita."""


def require_confirmation(action_name: str, confirmed: bool) -> None:
    """
    Garante que ações críticas só sigam com confirmação humana.
    """
    if not confirmed:
        raise ConfirmationRequired(
            f"Action '{action_name}' requires explicit confirmation."
        )
