# AGENTS.md

# Guia Operacional De Agentes H&A

Este documento define como agentes devem operar dentro do ecossistema H&A. Ele e normativo para auditoria, planejamento e implantacao assistida por agentes.

## Principio Central

Agentes devem preservar a soberania institucional do H&A. Toda intervencao deve respeitar o runtime real, os contratos existentes, a observabilidade operacional e a Regra de Ouro SSOT.

O agente nao deve otimizar por elegancia de codigo quando isso aumentar risco operacional. No H&A, a prioridade e continuidade, rastreabilidade e correcao incremental.

## Modelo Operacional Obrigatorio

Agentes devem operar sob o modelo ACI(R): Auditoria Institucional Controlada.

ACI(R) significa:

- analisar antes de modificar;
- separar evidencia de intervencao;
- observar runtime real acima de teoria arquitetural;
- identificar autoridade, estado, contratos, logs e riscos;
- nao corrigir automaticamente sem autorizacao explicita.

## Relacao Entre ACI(R), ICfactory, CIE-X E Lexicon

### ACI(R)

ACI(R) e o modo de auditoria e diagnostico. Ele deve ser usado para mapear riscos, duplicidades, violacoes de SSOT, drift arquitetural e desalinhamentos entre celulas.

### ICfactory

ICfactory e o metodo de implantacao. Ele deve ser usado para transformar achados em fases pequenas, seguras, testaveis e aprovadas.

### CIE-X

CIE-X e o modelo de analise estrutural contextual. Ele deve ser usado para avaliar excecoes, tensoes entre componentes e cenarios em que a arquitetura formal diverge do runtime real.

### Lexicon

O `LEXICON.md` e a base conceitual oficial. Agentes devem usar seus termos como referencia antes de introduzir novos conceitos institucionais.

## Filosofia Institucional Do H&A

O H&A evolui por ajustes cirurgicos, nao por reescrita ampla.

Agentes devem:

- preservar comportamento existente;
- preservar nomes, logs e contratos;
- evitar simplificacao agressiva;
- reduzir soberania difusa;
- corrigir uma autoridade por vez;
- evitar criar multiplas fontes de verdade;
- respeitar a historia operacional do codigo;
- manter o sistema auditavel.

## Soberania Institucional

Cada componente deve ter autoridade clara sobre seu dominio.

### PositionManager

O `PositionManager` e o SSOT de posicao.

Agentes devem trata-lo como autoridade para:

- existencia de posicao;
- abertura oficial;
- fechamento oficial;
- historico;
- PnL;
- duracao;
- resultado de trade;
- memoria pos-trade relacionada a posicoes.

Agentes nao devem transferir autoridade de posicao para `Executor`, UI, `SlotController`, ALO ou caches auxiliares.

### SlotController

O `SlotController` e o orquestrador operacional.

Ele coordena:

- slots;
- ciclo operacional por slot;
- locks transitorios;
- chamadas ao `Decision`;
- chamadas ao `Executor`;
- sincronizacao com `PositionManager`;
- cleanup operacional.

Ele nao deve ser tratado como SSOT de posicao.

### Executor

O `Executor` e camada de execucao.

Ele pode:

- executar ordens;
- simular ordens;
- validar constraints de exchange;
- retornar resultado de execucao.

Ele nao deve ser autoridade final de posicao, historico ou decisao de trade.

### ALO

ALO e fonte de inteligencia adaptativa global.

Ele pode:

- consumir eventos;
- produzir guidance;
- atualizar perfis;
- sugerir bloqueios ou liberacoes contextuais.

Ele nao deve executar ordens, fechar posicoes ou alterar locks diretamente.

## SSOT

Agentes devem respeitar a Regra de Ouro SSOT:

- "Existe posicao?" deve ser respondido pelo `PositionManager`.
- "A ordem foi executada?" deve ser respondido pelo `Executor`.
- "O slot esta ocupado?" deve ser respondido pelo `SlotController`.
- "O sistema esta running, draining ou locked?" deve ser respondido pelo controlador de estado institucional.
- "O mercado esta operavel?" deve ser respondido por MQII/Radar conforme contrato.
- "Pode comprar agora?" deve ser respondido por `Decision`.

Nenhum patch deve criar nova autoridade concorrente para o mesmo estado.

## Auditoria Passiva E Reconciliacao Ativa

Agentes devem separar rigorosamente auditoria passiva de reconciliacao ativa.

### Auditoria Passiva

Pode:

- ler arquivos;
- mapear chamadas;
- comparar estados;
- classificar riscos;
- produzir relatorio.

Nao pode:

- alterar estado;
- liberar lock;
- resetar slot;
- fechar posicao;
- corrigir divergencia automaticamente.

### Reconciliacao Ativa

Pode corrigir divergencias apenas quando:

- solicitada explicitamente;
- planejada;
- aprovada;
- limitada a um ajuste por vez;
- validada por criterio de sucesso.

## Regras De Alteracao De Arquivos

Agentes devem seguir estas regras:

1. Gerar plano antes de qualquer patch.
2. Propor diff minimo antes de modificar.
3. Aguardar aprovacao explicita antes de alterar arquivos.
4. Aplicar um patch por vez.
5. Alterar um arquivo por vez quando o usuario exigir.
6. Nao reescrever arquivos inteiros sem autorizacao explicita.
7. Nao simplificar arquivos.
8. Nao remover logica existente sem aprovacao.
9. Nao alterar multiplos modulos ao mesmo tempo sem aprovacao.
10. Preservar nomes, logs, contratos e comportamento existente.
11. Mostrar diff final apos aplicar patch.

## Fluxo Operacional Recomendado

Para qualquer correcao:

1. Entender o pedido e o escopo.
2. Ler o runtime real antes de propor mudanca.
3. Mapear autoridades envolvidas.
4. Verificar SSOT.
5. Identificar risco de regressao.
6. Gerar plano ICfactory.
7. Propor o menor diff possivel.
8. Aguardar aprovacao explicita.
9. Aplicar somente o diff aprovado.
10. Mostrar diff final.
11. Propor validacao pos-patch.

## Runtime Real Acima De Teoria

Agentes devem considerar o runtime real acima de diagramas, nomes de arquivos ou intencao historica.

Antes de classificar um componente como vivo, legado ou teste, o agente deve observar:

- imports reais;
- entrypoints;
- chamadas efetivas;
- conexoes de dependencias;
- testes existentes;
- uso por UI ou headless;
- efeitos colaterais em estado.

## Preservacao De Observabilidade

Logs sao parte da governanca institucional.

Agentes devem evitar:

- remover logs;
- renomear logs;
- reduzir mensagens diagnosticas;
- ocultar erros;
- trocar logs por abstracoes sem necessidade.

Quando um patch alterar fluxo operacional, a observabilidade deve ser preservada ou explicitamente discutida antes.

## Drift Arquitetural

Agentes devem evitar aumentar drift arquitetural.

Sinais de drift incluem:

- duas celulas governando o mesmo estado;
- dois executores com contratos divergentes;
- UI exibindo estado diferente do runtime;
- auditoria que corrige estado;
- caches tratados como autoridade;
- caminhos legados chamados por entrypoints vivos.

Quando drift for encontrado, o agente deve mapear primeiro e corrigir depois, via ICfactory.

## Principios De Evolucao Segura

- Um ajuste por vez.
- Uma autoridade por dominio.
- Um SSOT por estado critico.
- Contratos preservados ate migracao explicita.
- Runtime vivo primeiro.
- Testes antes e depois.
- Diffs pequenos.
- Logs preservados.
- Reconciliacao somente quando autorizada.
- Nenhuma limpeza oportunista durante correcao critica.

## Aplicacao Ao Contrato SELL

No contrato SELL do H&A:

- `SlotController` orquestra o SELL.
- `Executor` executa ou simula a ordem.
- `PositionManager` fecha oficialmente a posicao.
- O retorno do `Executor` deve preservar os campos consumidos pelo `SlotController`.
- O sistema deve evitar `double close`, posicao fantasma, historico perdido, duration zerado e lock orfao.

Qualquer mudanca nesse contrato deve seguir ICfactory, com diff minimo e aprovacao explicita.
