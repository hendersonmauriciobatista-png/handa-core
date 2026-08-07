# ============================================================
# Action Intent — ENUM FECHADO (FASE 3.2.1)
# ============================================================

from enum import Enum


class ActionIntent(str, Enum):
    SAFE_STOP = "SAFE_STOP"
    CLEAR_SAFE_STOP = "CLEAR_SAFE_STOP"
    SET_UI_MODE = "SET_UI_MODE"
    ENABLE_AUTO_INTENT = "ENABLE_AUTO_INTENT"
