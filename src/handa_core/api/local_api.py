"""
API Local UI ↔ H&A (v1.0)
Read-only por padrão. Fonte única da verdade: Core H&A.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time

app = FastAPI(title="H&A Local API", version="1.0")

# ---------------------------------------------------------------------
# ADAPTADORES (plugar no core real)
# Substitua estas funções para ler o estado REAL do H&A
# ---------------------------------------------------------------------

def get_system_state():
    return {
        "system_status": "RUNNING",   # STOPPED | RUNNING | DRAINING
        "mode": "MOCK",               # MOCK | LIVE
        "risk": "RISK_NORMAL",        # RISK_NORMAL | RISK_ELEVATED | RISK_BLOCKED
        "heartbeat": int(time.time())
    }

def get_slots_state():
    slots = {}
    for i in range(1, 13):
        slots[f"SLOT_{i:02d}"] = {
            "state": "IDLE",           # IDLE | MONITORING | CLOSED | ERROR
            "pair": None,
            "last_action": "Aguardando",
            "last_update": int(time.time())
        }
    return slots

def get_activity_state():
    return {
        "summary": "Sistema operando normalmente",
        "last_event": "Nenhuma ação recente"
    }

def get_connectivity_state():
    return {
        "status": "OK",               # OK | DELAYED | NO_FEED
        "last_update": int(time.time())
    }

# ---------------------------------------------------------------------
# MODELOS
# ---------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    timestamp: int

class CommandRequest(BaseModel):
    command: str

# ---------------------------------------------------------------------
# ENDPOINTS READ-ONLY
# ---------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "OK", "timestamp": int(time.time())}

@app.get("/state/system")
def state_system():
    return get_system_state()

@app.get("/state/slots")
def state_slots():
    return get_slots_state()

@app.get("/state/activity")
def state_activity():
    return get_activity_state()

@app.get("/state/connectivity")
def state_connectivity():
    return get_connectivity_state()

# ---------------------------------------------------------------------
# COMANDOS GLOBAIS (TRAVADOS EM MOCK)
# ---------------------------------------------------------------------

@app.post("/command")
def command(req: CommandRequest):
    system = get_system_state()
    if system.get("mode") == "MOCK":
        return {
            "result": "REJECTED",
            "reason": "MODE=MOCK"
        }
    # Em LIVE, encaminhar para o core (não implementar aqui agora)
    raise HTTPException(status_code=403, detail="LIVE command handler not enabled")
