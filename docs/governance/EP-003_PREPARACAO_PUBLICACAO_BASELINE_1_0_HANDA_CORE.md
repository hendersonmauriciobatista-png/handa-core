# EP-003 — PREPARAÇÃO DA PUBLICAÇÃO DA BASELINE 1.0 H&A CORE

## 1. Objetivo

Registrar o plano executivo para publicação controlada da Baseline 1.0 do H&A CORE no repositório Git oficial, preservando a composição documentada pela EP-002 e a estrutura oficial estabelecida pela EP-001.

Este documento possui finalidade exclusivamente preparatória. Não cria pré-requisitos, não reorganiza o workspace e não realiza publicação.

## 2. Pré-requisitos

A publicação da Baseline 1.0 depende obrigatoriamente de:

1. existência do README oficial;
2. existência do `.gitignore` oficial;
3. validação final da composição da Baseline;
4. aprovação formal do Product Owner.

### 2.1 Estado documental dos pré-requisitos

| Pré-requisito | Estado registrado pela EP-002 | Condição para continuidade |
|---|---|---|
| README oficial | Pendente | O arquivo deverá existir antes da publicação. |
| `.gitignore` oficial | Pendente | O arquivo deverá existir e refletir os critérios de exclusão antes da publicação. |
| Validação final da composição | Pendente | A composição efetiva deverá ser confrontada com a EP-002. |
| Aprovação formal do Product Owner | Pendente | A publicação dependerá de aprovação explícita. |

Nenhuma etapa de publicação poderá ser iniciada enquanto qualquer um desses pré-requisitos permanecer pendente.

## 3. Escopo da publicação

### 3.1 Artefatos que deverão ser publicados

Observados os critérios da EP-002, deverão ser publicados:

- código-fonte;
- documentação;
- recursos;
- testes;
- scripts;
- workflows;
- ferramentas;
- arquivos de configuração;
- estrutura oficial do repositório.

A publicação deverá preservar os nomes, conteúdos e relações documentais dos artefatos integrantes da Baseline.

### 3.2 Artefatos que não deverão ser publicados

Não deverão ser publicados:

- ambientes virtuais;
- caches;
- builds;
- diretórios `dist`;
- logs;
- arquivos temporários;
- artefatos gerados automaticamente.

A exclusão desses elementos da publicação não autoriza sua remoção do workspace durante esta atividade.

## 4. Estratégia de publicação

A publicação deverá ocorrer de forma incremental, organizada por domínios documentais e técnicos, utilizando commits semânticos e preservando a rastreabilidade da evolução do projeto.

### 4.1 Sequência executiva prevista

1. Confirmar formalmente o atendimento dos quatro pré-requisitos.
2. Validar a lista de artefatos integrantes e excluídos contra a EP-002.
3. Validar a correspondência da estrutura física com a EP-001.
4. Preparar o primeiro conjunto de artefatos de forma organizada por domínio.
5. Verificar integridade, nomes e localização antes de cada registro versionado.
6. Registrar cada conjunto por commit semântico correspondente ao seu domínio.
7. Repetir a preparação, verificação e o registro incremental até cobrir toda a Baseline.
8. Realizar a verificação final da composição versionada.
9. Confirmar documentalmente o atendimento dos critérios de aceitação.

Esta sequência registra apenas o plano. Nenhum commit, repositório, branch, tag ou publicação é criado nesta atividade.

### 4.2 Organização incremental por domínios

A separação incremental deverá observar exclusivamente as categorias já registradas na EP-002:

- estrutura oficial;
- documentação;
- código-fonte;
- recursos;
- testes;
- scripts;
- workflows;
- ferramentas;
- arquivos de configuração.

A ordem operacional entre esses conjuntos deverá preservar dependências e rastreabilidade sem alterar a composição da Baseline.

### 4.3 Commits semânticos

Cada commit deverá:

- representar um conjunto documentalmente identificável;
- indicar objetivamente o domínio incorporado;
- evitar mistura de domínios sem relação documental;
- preservar a correspondência entre o conteúdo versionado e a EP-002;
- não incluir artefatos classificados como excluídos.

Este documento não define mensagens concretas de commit nem executa versionamento.

## 5. Critérios de aceitação

A publicação da Baseline 1.0 será considerada concluída somente quando:

1. todos os artefatos integrantes da Baseline estiverem versionados;
2. o repositório refletir integralmente a estrutura oficial definida pela EP-001;
3. a composição da Baseline corresponder integralmente ao inventário e aos critérios da EP-002;
4. a integridade dos artefatos estiver preservada.

### 5.1 Evidências mínimas de aceitação

| Critério | Evidência requerida |
|---|---|
| Cobertura da Baseline | Correspondência verificável entre os artefatos versionados e a composição da EP-002. |
| Estrutura oficial | Árvore publicada compatível com a EP-001. |
| Exclusões | Ausência dos elementos classificados como não publicáveis. |
| Integridade | Nomes e conteúdos preservados em relação às origens validadas. |
| Rastreabilidade | Histórico incremental com commits semanticamente identificáveis. |

A ausência de qualquer evidência impede a declaração de publicação concluída.

## 6. Classificação

**PREPARAÇÃO DOCUMENTADA — PUBLICAÇÃO AINDA NÃO AUTORIZADA.**

Fundamentação:

- o plano executivo está registrado;
- a estrutura oficial encontra-se materializada;
- a composição inicial está inventariada pela EP-002;
- README oficial, `.gitignore` oficial, validação final e aprovação formal do Product Owner permanecem pendentes;
- nenhuma publicação foi realizada.

## 7. Resumo Executivo

O plano executivo para publicação da Baseline 1.0 foi estabelecido com escopo de inclusão e exclusão, estratégia incremental por domínios, uso futuro de commits semânticos e critérios objetivos de aceitação. O estado permanece “Preparação documentada — publicação ainda não autorizada”, pois os quatro pré-requisitos obrigatórios continuam pendentes. Nenhum artefato foi publicado ou reorganizado.

## 8. Declaração de conformidade

Nenhum arquivo existente foi alterado, movido, copiado, renomeado ou removido. Nenhum código, arquitetura, documentação, configuração ou recurso existente foi modificado. O documento registra exclusivamente o plano executivo para publicação da Baseline 1.0 do H&A CORE. Nenhuma publicação foi realizada e nenhuma atividade posterior foi iniciada.
