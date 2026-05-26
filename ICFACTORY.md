# ICFACTORY.md

# Metodo ICfactory H&A / ACI(R)

Este documento formaliza o metodo ICfactory utilizado no ecossistema H&A/ACI(R). O ICfactory organiza criacao, analise, implantacao, validacao e registro institucional de mudancas, preservando SSOT, soberania, contratos e runtime real.

## 1. Definicao Geral

ICfactory e um metodo institucional de evolucao controlada. Ele transforma diagnosticos em mudancas pequenas, aprovadas, auditaveis e validadas.

O ICfactory nao e um produto unico, nem uma ferramenta isolada. E um metodo operacional composto por celulas com responsabilidades distintas.

## 2. Diferenca Entre Conceito E Produto

### Conceito

Conceito pertence ao metodo.

Ele define:

- linguagem;
- principios;
- celulas;
- responsabilidades;
- criterios de governanca;
- limites de autoridade.

### Produto

Resultado pertence ao sistema.

Ele pode ser:

- patch aplicado;
- relatorio;
- plano;
- teste;
- documento;
- validacao;
- registro institucional.

O conceito orienta. O produto entrega.

## 3. Fluxo Oficial Do ICfactory

1. Criação identifica ou estrutura a necessidade.
2. ARCHON valida fronteiras arquiteturais.
3. ACI(R) audita o estado real sem alterar.
4. CIE-X analisa tensoes estruturais e excecoes contextuais.
5. Desenvolvimento propoe ajuste minimo.
6. Implantação aplica somente o patch aprovado.
7. Testar / QA-IA valida comportamento, regressao e contrato.
8. Registrar / R-IA documenta decisao, resultado e aprendizado.
9. ADA e MCA acompanham melhoria adaptativa e impacto institucional.

## 4. Politica De Patch Minimo

Toda mudanca deve buscar o menor diff capaz de resolver o problema aprovado.

Patch minimo significa:

- alterar apenas o necessario;
- preservar nomes;
- preservar logs;
- preservar contratos;
- preservar comportamento colateral conhecido;
- evitar limpeza oportunista;
- evitar refatoracao ampla;
- nao reescrever arquivo inteiro sem autorizacao explicita.

## 5. Regra De Um Ajuste Por Vez

Cada patch deve resolver uma unidade institucional de risco.

Nao se deve:

- corrigir multiplos dominios simultaneamente;
- mudar varios modulos sem necessidade;
- misturar bugfix com limpeza;
- misturar auditoria com reconciliacao;
- corrigir arquitetura inteira em uma etapa.

## 6. Separacao Entre Auditoria E Mutacao

Auditoria observa.

Mutacao altera.

No ICfactory, essas fases devem permanecer separadas. Um agente pode auditar, mapear e propor; ele so deve modificar apos aprovacao explicita.

## 7. Aprovacao Explicita

Nenhum patch deve ser aplicado sem aprovacao clara do operador.

A aprovacao deve corresponder ao escopo do patch. Se o patch proposto mudar, a aprovacao deve ser solicitada novamente.

## 8. Preservacao Institucional

O ICfactory preserva:

- SSOT;
- soberania institucional;
- contratos existentes;
- observabilidade;
- logs;
- runtime real;
- compatibilidade operacional;
- rastreabilidade.

## 9. Prevencao De Drift Arquitetural

O ICfactory combate drift arquitetural por meio de:

- mapas de autoridade;
- auditoria passiva;
- patches pequenos;
- registro de decisoes;
- classificacao de runtime, teste e legado;
- consolidacao gradual de SSOT.

# Celulas Principais

## 10. Criação

### Definicao

Criação e a celula responsavel por formular a intencao inicial, nomear o problema e estabelecer o objetivo institucional.

### Objetivo

Transformar uma necessidade difusa em escopo claro.

### Responsabilidade

- identificar o problema;
- formular objetivo;
- definir restricoes;
- preservar contexto de negocio e runtime;
- preparar entrada para ACI(R), ARCHON ou Desenvolvimento.

### O que NAO deve fazer

- aplicar patch;
- decidir arquitetura final sozinha;
- remover codigo;
- transformar intuicao em mudanca sem auditoria.

### Relacao com as demais celulas

Criação inicia o fluxo e alimenta ARCHON, ACI(R) e CIE-X.

### Impacto institucional no H&A

Evita que mudancas comecem sem objetivo claro ou sem fronteira institucional.

## 11. Desenvolvimento

### Definicao

Desenvolvimento e a celula que converte plano aprovado em proposta tecnica de mudanca.

### Objetivo

Produzir o menor diff viavel para o ajuste aprovado.

### Responsabilidade

- propor diff minimo;
- preservar contratos;
- manter nomes e logs;
- limitar escopo;
- aguardar aprovacao antes de aplicar.

### O que NAO deve fazer

- reescrever arquivo inteiro sem autorizacao;
- simplificar agressivamente;
- refatorar por gosto;
- alterar multiplos modulos sem necessidade.

### Relacao com as demais celulas

Recebe insumos de ACI(R), CIE-X e ARCHON; entrega para Implantação.

### Impacto institucional no H&A

Garante que correcao tecnica nao viole soberania institucional nem runtime real.

## 12. Implantação

### Definicao

Implantação e a celula que aplica o patch aprovado.

### Objetivo

Executar somente a mudanca autorizada, sem expansao de escopo.

### Responsabilidade

- aplicar um patch por vez;
- alterar apenas arquivos autorizados;
- mostrar diff final;
- preservar rastreabilidade.

### O que NAO deve fazer

- aplicar patch nao aprovado;
- corrigir itens adjacentes;
- mudar arquivos adicionais;
- executar reconciliacao sem pedido.

### Relacao com as demais celulas

Recebe diff aprovado de Desenvolvimento e entrega para QA-IA.

### Impacto institucional no H&A

Reduz regressao e mantem controle humano sobre mudancas criticas.

## 13. Testar / QA-IA

### Definicao

QA-IA e a celula de validacao automatizada e assistida por inteligencia.

### Objetivo

Confirmar que o ajuste resolveu o problema sem gerar regressao.

### Responsabilidade

- definir testes antes e depois;
- observar estados criticos;
- verificar logs;
- identificar sintomas de falha;
- validar contratos e SSOT.

### O que NAO deve fazer

- alterar codigo para fazer teste passar sem aprovacao;
- mascarar falha;
- substituir auditoria por suposicao.

### Relacao com as demais celulas

Recebe patch da Implantação e gera insumos para R-IA, ADA e MCA.

### Impacto institucional no H&A

Garante que mudancas pequenas sejam realmente seguras no runtime.

## 14. Registrar / R-IA

### Definicao

R-IA e a celula de registro institucional assistido por inteligencia.

### Objetivo

Documentar decisao, evidencia, patch, risco e resultado.

### Responsabilidade

- registrar o que mudou;
- registrar por que mudou;
- registrar riscos aceitos;
- preservar contexto para auditorias futuras;
- alimentar memoria institucional.

### O que NAO deve fazer

- alterar codigo;
- reclassificar decisao sem evidencia;
- substituir testes.

### Relacao com as demais celulas

Recebe saidas de QA-IA, Implantação e ACI(R).

### Impacto institucional no H&A

Reduz perda de contexto e previne repeticao de erros arquiteturais.

# Celulas Avancadas

## 15. ARCHON

### Definicao

ARCHON e a celula de guarda arquitetural. Ela valida fronteiras, ownership e soberania entre componentes.

### Objetivo

Evitar que uma correcao local viole a arquitetura institucional.

### Responsabilidade

- mapear autoridade;
- proteger SSOT;
- validar limites de celulas;
- identificar risco de drift;
- orientar ordem segura de mudanca.

### O que NAO deve fazer

- aplicar patch;
- substituir QA;
- transformar governanca em refatoracao ampla.

### Relacao com as demais celulas

ARCHON orienta Desenvolvimento, ACI(R), CIE-X e Implantação.

### Impacto institucional no H&A

Mantem a Constituicao Soberana do H&A aplicavel em mudancas reais.

## 16. OSE

### Definicao

OSE e a celula de Observabilidade Sistemica Estrutural.

### Objetivo

Garantir que estados, logs, eventos e sintomas operacionais permaneçam visiveis.

### Responsabilidade

- identificar logs criticos;
- preservar observabilidade;
- mapear sintomas de falha;
- orientar monitoramento antes/depois.

### O que NAO deve fazer

- remover logs;
- reduzir diagnostico;
- alterar runtime sem aprovacao.

### Relacao com as demais celulas

OSE apoia ACI(R), QA-IA, R-IA e Desenvolvimento.

### Impacto institucional no H&A

Evita patches cegos e reduz risco de falha silenciosa.

## 17. CIE-X

### Definicao

CIE-X e a celula de inteligencia contextual estrutural para excecoes controladas.

### Objetivo

Analisar situacoes em que regra, contexto e runtime entram em tensao.

### Responsabilidade

- avaliar excecoes;
- distinguir regra de caso contextual;
- evitar congelamento operacional;
- manter excecoes rastreaveis.

### O que NAO deve fazer

- burlar SSOT;
- transformar excecao em padrao;
- autorizar patch sem ICfactory;
- ignorar risco.

### Relacao com as demais celulas

CIE-X apoia ARCHON, ACI(R), Decision, ALO e Desenvolvimento.

### Impacto institucional no H&A

Permite flexibilidade sem perder governanca.

## 18. ACI(R)

### Definicao

ACI(R) e Auditoria Institucional Controlada.

### Objetivo

Analisar estado real sem alterar arquivos ou runtime.

### Responsabilidade

- localizar duplicidades;
- detectar violacoes de SSOT;
- mapear dependencias;
- classificar riscos;
- produzir relatorio tecnico.

### O que NAO deve fazer

- aplicar patch;
- reconciliar estado;
- remover codigo;
- executar correcao automatica.

### Relacao com as demais celulas

ACI(R) alimenta ICfactory, ARCHON, CIE-X e QA-IA.

### Impacto institucional no H&A

Fornece evidencia antes da intervencao.

## 19. MCA

### Definicao

MCA e a celula de Memoria Cognitiva Arquitetural.

### Objetivo

Preservar aprendizado arquitetural acumulado.

### Responsabilidade

- registrar padroes;
- lembrar decisoes;
- conectar incidentes recorrentes;
- apoiar prevencao de drift.

### O que NAO deve fazer

- decidir patch sozinha;
- substituir R-IA;
- alterar runtime.

### Relacao com as demais celulas

MCA consome registros de R-IA e evidencia de ACI(R), apoiando ARCHON e ADA.

### Impacto institucional no H&A

Evita perda de memoria institucional entre ciclos de evolucao.

## 20. ADA

### Definicao

ADA e a celula de Adaptacao Dirigida por Aprendizado.

### Objetivo

Usar aprendizado institucional para orientar proximas melhorias.

### Responsabilidade

- identificar padroes de falha;
- sugerir proximas fases;
- priorizar risco;
- conectar QA, R-IA e ALO.

### O que NAO deve fazer

- aplicar mudancas automaticas;
- ultrapassar aprovacao humana;
- substituir Decision ou PositionManager.

### Relacao com as demais celulas

ADA recebe sinais de QA-IA, R-IA, MCA e ALO.

### Impacto institucional no H&A

Transforma validacoes e incidentes em evolucao segura.

## 21. XAI-L

### Definicao

XAI-L e a celula de explicabilidade local.

### Objetivo

Explicar decisoes, rejeicoes, bloqueios e efeitos de patch em linguagem rastreavel.

### Responsabilidade

- produzir explicacoes tecnicas;
- diferenciar causa e sintoma;
- conectar logs a decisoes;
- apoiar auditoria e QA.

### O que NAO deve fazer

- inventar causalidade sem evidencia;
- alterar decisao operacional;
- substituir logs reais.

### Relacao com as demais celulas

XAI-L apoia ACI(R), OSE, QA-IA, CIE-X e R-IA.

### Impacto institucional no H&A

Melhora confianca e interpretabilidade das mudancas.

## 22. OCP

### Definicao

OCP e a celula de Controle de Politica Operacional.

### Objetivo

Garantir que mudancas respeitem politicas, contratos e limites de operacao.

### Responsabilidade

- validar regras permanentes;
- checar escopo autorizado;
- proteger contratos;
- impedir mudancas fora de politica.

### O que NAO deve fazer

- decidir arquitetura sem ARCHON;
- aplicar patch;
- flexibilizar regra sem aprovacao.

### Relacao com as demais celulas

OCP atua junto de Implantação, Desenvolvimento e ARCHON.

### Impacto institucional no H&A

Evita alteracoes agressivas ou fora de governanca.

## 23. ETO

### Definicao

ETO e a celula de Execucao Tecnica Operacional.

### Objetivo

Executar tarefas tecnicas aprovadas com precisao e baixo ruido.

### Responsabilidade

- aplicar comandos autorizados;
- coletar saidas;
- executar testes;
- gerar diffs;
- manter escopo.

### O que NAO deve fazer

- executar comando destrutivo sem aprovacao;
- alterar arquivos fora do escopo;
- aplicar patch nao aprovado.

### Relacao com as demais celulas

ETO serve Implantação, QA-IA e ACI(R).

### Impacto institucional no H&A

Transforma decisao institucional em acao tecnica controlada.

# 24. Aplicacao Ao H&A

No H&A, o ICfactory deve ser usado especialmente para mudancas que tocam:

- `PositionManager`;
- `Executor`;
- `SlotController`;
- `AutoLoop`;
- `Decision`;
- `Selection`;
- `Radar`;
- ALO;
- MQII;
- DRC;
- UI/runtime.

Mudancas nesses componentes podem afetar dinheiro, estado, posicao, locks, historico e observabilidade. Por isso devem seguir o fluxo institucional completo.

# 25. Clausula Final

O ICfactory existe para proteger o H&A de correcoes grandes demais, rapidas demais ou ambiguas demais.

Toda evolucao deve responder:

- qual autoridade esta sendo alterada?
- qual SSOT esta sendo preservado?
- qual contrato permanece?
- qual risco foi reduzido?
- qual teste confirma?
- qual log comprova?
- qual registro permanece?

Sem essas respostas, a mudanca ainda nao esta pronta para implantacao.
