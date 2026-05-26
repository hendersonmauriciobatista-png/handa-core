# CONSTITUTION.md

# Constituicao Soberana Do H&A

Este documento define os principios institucionais de autoridade, estado e governanca operacional do H&A.

## 1. Regra De Ouro SSOT

Todo estado critico deve possuir uma unica fonte oficial de verdade.

Nenhum componente deve criar autoridade concorrente sobre o mesmo dominio de estado. Caches, snapshots, copias locais e estados auxiliares podem existir, mas nao podem substituir o SSOT institucional.

## 2. PositionManager

O `PositionManager` e o SSOT de posicao.

Ele governa:

- existencia de posicoes abertas;
- abertura oficial de posicao;
- fechamento oficial de posicao;
- historico de trades;
- PnL;
- duracao;
- motivo de fechamento;
- memoria operacional pos-trade relacionada a posicoes.

Nenhum outro componente deve ser autoridade final para responder se uma posicao existe.

## 3. Executor

O `Executor` executa ordens.

Ele pode:

- executar BUY;
- executar SELL;
- simular execucao em modo mock;
- validar restricoes de exchange;
- retornar resultado de execucao.

O `Executor` nao governa posicao oficial, historico oficial, DRC, slot state ou decisao de trade.

## 4. SlotController

O `SlotController` orquestra slots e rito operacional.

Ele governa:

- ocupacao de slots;
- transicoes operacionais de slot;
- reserva operacional;
- locks transitorios de simbolo;
- chamada ao `Decision`;
- chamada ao `Executor`;
- sincronizacao com `PositionManager`;
- cleanup operacional apos BUY/SELL.

O `SlotController` nao e SSOT de posicao.

## 5. AutoLoop

O `AutoLoop` e o relogio do runtime.

Ele governa:

- inicio e parada do ciclo;
- contagem de ciclos;
- latencias;
- heartbeat operacional;
- chamada periodica ao `SlotController`.

O `AutoLoop` nao decide trade, nao escolhe ativo, nao executa ordens e nao governa posicoes.

## 6. Decision

O `Decision` autoriza o BUY final.

Ele governa:

- autorizacao final de entrada;
- validacao de contexto sistemico;
- avaliacao de risco/capital;
- bloqueios finais de entrada;
- emissao ou rejeicao de `BuySignal`.

O `Decision` nao executa ordens, nao fecha posicoes e nao governa slots.

## 7. Selection

O `Selection` define elegibilidade estrutural.

Ele governa:

- validacao estrutural de candidato;
- score de selecao;
- razoes estruturais de aprovacao ou rejeicao;
- ordenacao de oportunidades estruturalmente elegiveis, quando aplicavel.

O `Selection` nao executa ordens, nao governa posicoes e nao autoriza BUY final sozinho.

## 8. Radar

O `Radar` gera oportunidades.

Ele governa:

- leitura de mercado;
- ranking de ativos;
- publicacao de oportunidades;
- contexto de liquidez;
- sinais de rejeicao de radar.

O `Radar` nao executa ordens, nao ocupa slots e nao governa posicoes.

## 9. MQII

O MQII mede qualidade de mercado.

Ele governa:

- estado macro de qualidade;
- classificacao de ambiente operacional;
- sinalizacao de mercado fraco, cauteloso, operavel ou agressivo;
- contexto para filtros dinamicos.

MQII nao executa ordens, nao fecha posicoes e nao substitui o `Decision`.

## 10. ALO

ALO governa inteligencia adaptativa global.

Ele governa:

- aprendizado a partir de eventos;
- perfis por simbolo;
- memoria adaptativa;
- guidance contextual;
- sugestoes de bloqueio, cautela ou liberacao.

ALO nao executa ordens, nao fecha posicoes, nao altera locks diretamente e nao substitui o SSOT.

## 11. DRC

DRC governa reentrada e cooldown pos-trade.

Ele governa:

- cooldown apos loss;
- cooldown apos win;
- bloqueios de reentrada;
- classificacao de fast stop, quick stop, stagnation e exaustao;
- memoria pos-trade para evitar repeticao operacional ruim.

DRC nao executa ordens e nao cria posicao.

## 12. Auditoria

Auditoria observa sem alterar.

Ela pode:

- ler estados;
- comparar fontes;
- detectar divergencias;
- classificar severidade;
- gerar relatorios;
- recomendar reconciliacao.

Auditoria nao libera locks, nao fecha posicoes, nao reseta slots e nao corrige estado.

## 13. Reconciliacao

Reconciliacao corrige apenas quando chamada explicitamente.

Ela pode:

- corrigir locks orfaos;
- tratar posicao fantasma;
- realinhar slot com posicao autoritativa;
- escalar divergencia critica.

Reconciliacao nao deve ocorrer de forma silenciosa dentro de auditoria passiva.

## 14. UI

UI comanda e observa.

Ela pode:

- solicitar start;
- solicitar drain;
- solicitar lock/unlock;
- solicitar reset;
- exibir estado;
- exibir posicoes, slots, metricas e alertas.

UI nao deve mutar estado critico diretamente. Comandos devem passar por controladores institucionais.

## 15. Principio Final

O H&A deve evoluir por alteracoes pequenas, aprovadas e auditaveis.

Toda correcao deve preservar:

- contratos existentes;
- logs;
- rastreabilidade;
- runtime real;
- SSOT;
- soberania institucional;
- comportamento operacional.
