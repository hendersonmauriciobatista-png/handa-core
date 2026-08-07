# ============================================================
# H&A — R-IA PATCH RECORD
# ============================================================

Patch ID: WFD-001  
Nome: Whale Flow Detection  
Tipo: Evolução de Inteligência de Mercado  
Classificação: P2  
Status: CONGELADO  
Data: 2026-04-05  
Origem: Planejamento estratégico / análise prospectiva  

---

## 📌 Definição

Camada futura destinada a identificar e aproveitar movimentos institucionais saudáveis (“fluxo de baleias”) sem perseguir spikes isolados, pumps terminais ou exaustões de curto prazo.

---

## 🎯 Objetivo

Melhorar a qualidade das entradas do H&A por meio da detecção de continuidade de fluxo, persistência de volume e força estrutural, distinguindo movimento saudável de armadilhas de mercado.

---

## 🧠 Princípios Oficiais

1. Não reagir a spikes únicos de volume  
2. Priorizar persistência de força em múltiplos ciclos  
3. Exigir contexto estrutural válido (tendência, momentum, volume e não esticamento extremo)  
4. Diferenciar fluxo saudável de pump terminal  
5. Não servir para forçar entradas nem aumentar agressividade do sistema  
6. Servir apenas para elevar a qualidade da decisão e reduzir armadilhas  

---

## ⚙️ Critérios Conceituais

- volume_ratio elevado com persistência em múltiplos ciclos  
- EMA structure válida (EMA10 > EMA20 > EMA50)  
- momentum consistente e não reversivo  
- RSI em zona saudável (evitando extremos)  
- ausência de esticamento excessivo em relação às médias  

---

## 🔌 Interface Conceitual (Futura)

```python
class WhaleFlowSignal:
    is_whale_flow: bool
    flow_strength: float
    persistence: int
    is_exhaustion: bool
    is_valid_flow: bool
Radar → WFD → SelectionPolicy → DecisionEngine → ALO Decision



