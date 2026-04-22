# =============================================================================
# core/selection_dynamic/policy_modes.py
# H&A — Selection Dynamic Policy Modes
# =============================================================================

from enum import Enum


class SelectionPolicyMode(str, Enum):
    """
    Define o modo operacional da Selection Policy Dinâmica.

    Cada modo altera o nível de exigência do sistema
    para aprovação de trades.
    """

    DEFENSIVE = "DEFENSIVE"
    BALANCED = "BALANCED"
    OPPORTUNITY = "OPPORTUNITY"


# =============================================================================
# HELPERS
# =============================================================================

def is_defensive(mode: SelectionPolicyMode) -> bool:
    return mode == SelectionPolicyMode.DEFENSIVE


def is_balanced(mode: SelectionPolicyMode) -> bool:
    return mode == SelectionPolicyMode.BALANCED


def is_opportunity(mode: SelectionPolicyMode) -> bool:
    return mode == SelectionPolicyMode.OPPORTUNITY