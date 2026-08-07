# ============================================================
# H&A — R-IA PATCH RECORD
# ============================================================

Patch ID: TREND-HOLD-001  
Nome: Hold em Tendência  
Tipo: Evolução de Gestão de Saída  
Classificação: P3  
Status: CONGELADO  
Data: 2026-04-05  
Origem: Planejamento estratégico / análise prospectiva  

---

## 📌 Definição

Patch futuro destinado a reduzir saídas prematuras em movimentos saudáveis de continuação, permitindo que o H&A permaneça mais tempo em trades lucrativos quando houver apenas pullback leve ou ruído normal de tendência.

---

## 🎯 Objetivo

Aumentar a captura de movimento do H&A em cenários favoráveis, evitando que a posição seja encerrada cedo demais por pequenas devoluções de lucro que ainda não caracterizam enfraquecimento real da tendência.

---

## 🧠 Princípios Oficiais

1. Não remover proteção estrutural do sistema  
2. Não enfraquecer hard stop, stop fixo ou lógica de defesa  
3. Não transformar o H&A em sistema agressivo  
4. Permitir respiração maior da posição apenas quando houver lucro e devolução pequena  
5. Melhorar captura de tendência sem comprometer preservação de capital  

---

## ⚙️ Conceito Operacional

Antes de encerrar a posição por mecanismos dinâmicos de proteção, o sistema deve avaliar se a devolução atual do lucro ainda é pequena e compatível com ruído normal de tendência.

Se o trade ainda estiver positivo e o giveback for pequeno, a posição deve continuar aberta.

---

## 🔧 Bloco Conceitual Congelado

```python
# =========================
# HOLD EM TENDÊNCIA (PATCH 2 - CONGELADO)
# =========================
if pnl_pct > 0:

    # evita sair cedo em tendência saudável
    small_giveback = (pos.peak_pnl_pct - pnl_pct) < (PROFIT_GIVEBACK_LEVEL_1 * 0.5)

    if small_giveback:
        return None