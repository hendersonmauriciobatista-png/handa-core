# UI – H&A (Interface de Observação)

Esta pasta contém exclusivamente a **interface do sistema H&A**.

A UI foi projetada para ser **observacional, segura e não intrusiva**, refletindo fielmente o estado do H&A sem interferir na sua lógica interna.

---

## Princípios Fundamentais

- A UI **não decide** nada.
- A UI **não executa trades**.
- A UI **não contém lógica de estratégia**.
- A UI **apenas reflete estados** vindos do H&A.
- Slots são **entidades autônomas**, sem controle individual pela UI.
- **Ações são apenas globais** (START, STOP, LIVE, EMERGENCY).

---

## Estrutura de Pastas

- `views/`  
  Renderização visual. Nenhuma decisão ou regra de negócio.

- `state/`  
  Estados somente leitura recebidos do H&A.

- `controllers/`  
  Orquestra eventos da interface (cliques, foco, timers), sem lógica de decisão.

- `services/`  
  Comunicação com o H&A conforme contrato UI ↔ H&A.

- `security/`  
  Entrada de API keys e integração com Secure Storage do sistema operacional.

- `logs/`  
  Visualização de logs em modo read-only.

- `utils/`  
  Utilidades neutras (timers, formatadores, constantes).

---

## Regras de Ouro

- Nenhum arquivo da UI contém lógica de trading.
- Nenhum segredo é persistido em texto plano.
- Nenhuma view acessa diretamente o H&A.
- Controllers não tomam decisões.
- Se a UI cair, o H&A continua operando.
- Se o H&A cair, a UI apenas reflete o estado.

---

## Filosofia de Uso

A UI do H&A é uma **sala de controle**, não um cockpit de trader manual.

Ela foi desenhada para:
- reduzir erro humano
- evitar ansiedade operacional
- permitir leitura rápida do sistema
- suportar operação LIVE com segurança

---

## Status

**UI H&A v1.0**  
Definida, validada pelo QA IA e pronta para implementação.
