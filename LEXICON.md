# LEXICON.md

# Dicionario Institucional H&A / ACI(R)

Este documento formaliza termos institucionais usados no ecossistema H&A. Seu objetivo e reduzir ambiguidade sem alterar arquitetura, codigo ou contratos operacionais.

## ICfactory

### Definicao
ICfactory e o metodo de implantacao controlada do H&A para evoluir componentes criticos por fases pequenas, auditaveis e reversiveis.

### Objetivo
Permitir correcao institucional sem regressao operacional, evitando refatoracoes amplas, alteracoes em massa ou perda de rastreabilidade.

### Funcao institucional
Organizar mudancas em fases, cada uma com objetivo, risco, teste de validacao e criterio de sucesso.

### O que NAO significa
Nao significa simplificar arquivos, remover logica existente, reescrever modulos inteiros ou aplicar modernizacao ampla sem autorizacao.

### Relacao com o H&A
No H&A, ICfactory e o mecanismo recomendado para corrigir contratos sensiveis, como o contrato SELL entre `SlotController`, `Executor` e `PositionManager`.

## CIE-X

### Definicao
CIE-X e uma camada de excecao contextual controlada usada para evitar congelamento operacional quando o sistema encontra oportunidades premium em condicoes moderadas ou cautelosas.

### Objetivo
Permitir recuperacao contextual sem romper a disciplina institucional de risco.

### Funcao institucional
Atuar como excecao governada: libera ou flexibiliza determinados bloqueios apenas quando criterios fortes e rastreaveis sao satisfeitos.

### O que NAO significa
Nao significa ignorar risco, forcar trade, burlar `Decision` ou transformar excecao em regra padrao.

### Relacao com o H&A
No H&A, CIE-X aparece como mecanismo de liberacao premium controlada dentro de fluxos de selecao e decisao.

## ACI(R)

### Definicao
ACI(R) significa Auditoria Institucional Controlada: modo de analise tecnica que observa arquitetura, autoridade, estado e risco sem modificar arquivos.

### Objetivo
Produzir diagnosticos confiaveis antes de qualquer patch, separando evidencia de intervencao.

### Funcao institucional
Mapear duplicidades, violacoes de SSOT, drift arquitetural, locks orfaos, divergencias runtime/UI e conflitos de soberania.

### O que NAO significa
Nao significa corrigir automaticamente, refatorar, limpar codigo ou executar reconciliacao ativa.

### Relacao com o H&A
No H&A, ACI(R) e o protocolo usado para auditar celulas como `AutoLoop`, `SlotController`, `PositionManager`, `Executor`, `Radar`, `Selection` e `Decision`.

## Lexicon

### Definicao
Lexicon e o dicionario institucional que define termos, limites e responsabilidades conceituais do ecossistema H&A.

### Objetivo
Criar linguagem comum entre auditoria, desenvolvimento, runtime e governanca.

### Funcao institucional
Evitar que termos como "autoridade", "reconciliacao", "SSOT" ou "drift" sejam usados de forma ambigua.

### O que NAO significa
Nao significa documentacao de API, especificacao de codigo ou plano de implementacao.

### Relacao com o H&A
Este arquivo e o Lexicon inicial do H&A e deve servir como referencia para auditorias e planos ICfactory.

## SSOT

### Definicao
SSOT significa Single Source of Truth: uma unica fonte oficial para responder por determinado dominio de estado.

### Objetivo
Eliminar conflito entre copias paralelas de estado e reduzir decisoes concorrentes.

### Funcao institucional
Definir qual celula responde por cada pergunta critica. Exemplo: "existe posicao?" deve ser respondido pelo `PositionManager`.

### O que NAO significa
Nao significa que outros componentes nao possam manter caches, snapshots ou estados auxiliares. Significa que eles nao podem ser autoridade final.

### Relacao com o H&A
No H&A, o `PositionManager` deve ser o SSOT de posicoes, enquanto `Executor`, `SlotController` e UI devem operar a partir desse contrato.

## Soberania Institucional

### Definicao
Soberania Institucional e a autoridade formal de uma celula sobre um dominio especifico da arquitetura.

### Objetivo
Evitar que multiplos componentes decidam a mesma coisa com criterios diferentes.

### Funcao institucional
Separar responsabilidades como execucao, posicao, decisao, selecao, runtime, UI, auditoria e reconciliacao.

### O que NAO significa
Nao significa isolamento absoluto. Componentes podem colaborar, mas nao devem invadir dominios de autoridade alheios.

### Relacao com o H&A
No H&A, soberania institucional define que `Executor` executa ordens, `PositionManager` governa posicoes e `SlotController` orquestra slots.

## Drift Arquitetural

### Definicao
Drift Arquitetural e o afastamento gradual entre a arquitetura pretendida e a arquitetura real executada pelo codigo.

### Objetivo
Identificar acumulacao de caminhos paralelos, duplicidades historicas, contratos divergentes e componentes fossilizados.

### Funcao institucional
Servir como alerta para auditorias e planos de correcao incremental.

### O que NAO significa
Nao significa que todo codigo antigo deve ser removido imediatamente.

### Relacao com o H&A
No H&A, sinais de drift incluem coexistencia de `core`, `h_a`, `legacy`, `ui`, `interface`, `executor` raiz e `core/executor`.

## Reconciliacao Ativa

### Definicao
Reconciliacao Ativa e o processo explicito de corrigir divergencias reais entre fontes de estado.

### Objetivo
Restaurar consistencia institucional quando auditoria detecta estado impossivel, lock orfao, posicao fantasma ou slot desalinhado.

### Funcao institucional
Aplicar correcoes controladas, rastreaveis e autorizadas em estados operacionais.

### O que NAO significa
Nao significa auditoria passiva, correcao silenciosa ou mutacao escondida dentro de funcoes diagnosticas.

### Relacao com o H&A
No H&A, reconciliacao ativa deve ser chamada explicitamente e nao deve se confundir com `_audit_operational_consistency`.

## Auditoria Passiva

### Definicao
Auditoria Passiva e a observacao estrutural sem modificacao de estado.

### Objetivo
Detectar riscos e inconsistencias sem interferir no runtime.

### Funcao institucional
Comparar snapshots, listar divergencias, classificar severidade e recomendar reconciliacao quando necessario.

### O que NAO significa
Nao significa corrigir slots, liberar locks, fechar posicoes ou resetar componentes.

### Relacao com o H&A
No H&A, ACI(R) deve operar como auditoria passiva ate que uma reconciliacao ativa seja autorizada.

## Inteligencia Funcional Local

### Definicao
Inteligencia Funcional Local e a capacidade de uma celula tomar decisoes dentro de seu proprio dominio, usando contexto limitado e responsabilidade clara.

### Objetivo
Permitir que cada componente seja competente sem se tornar soberano sobre o sistema inteiro.

### Funcao institucional
Dar autonomia local a celulas como `Selection`, `Decision`, `MQII`, `DRC` e `Executor`.

### O que NAO significa
Nao significa inteligencia global, autoridade irrestrita ou decisao fora do dominio da celula.

### Relacao com o H&A
No H&A, `Selection` pode avaliar elegibilidade estrutural, mas nao deve executar BUY; `Executor` pode executar ordem, mas nao deve governar posicao oficial.

## Inteligencia Adaptativa Global

### Definicao
Inteligencia Adaptativa Global e a capacidade do sistema aprender com eventos agregados e ajustar orientacoes de forma controlada.

### Objetivo
Melhorar comportamento institucional ao longo do tempo sem perder rastreabilidade ou violar soberanias locais.

### Funcao institucional
Gerar perfis, memoria, penalidades, guidance e recomendacoes a partir de resultados historicos.

### O que NAO significa
Nao significa substituir `Decision`, executar ordens, fechar posicoes ou alterar locks diretamente.

### Relacao com o H&A
No H&A, ALO representa a inteligencia adaptativa global, consumindo eventos e produzindo guidance para outras celulas.

## Runtime Institucional

### Definicao
Runtime Institucional e o conjunto de componentes vivos que operam o ciclo real do H&A em execucao.

### Objetivo
Definir o caminho operacional oficial e separar runtime vivo de testes, legado e prototipos.

### Funcao institucional
Preservar previsibilidade do sistema, garantindo que comandos, estados e eventos sigam autoridades formais.

### O que NAO significa
Nao significa todos os arquivos do repositorio, todos os entrypoints ou toda logica historica presente no codigo.

### Relacao com o H&A
No H&A, o runtime institucional atual passa principalmente por `AutoLoop`, `SlotController`, `Radar`, `Decision`, `Executor` e `PositionManager`.
