# EP-002 — BASELINE 1.0 DO H&A CORE

## 1. Objetivo

Definir a Baseline 1.0 oficial do H&A CORE exclusivamente a partir dos artefatos e diretórios existentes no workspace na data desta consolidação.

A Baseline registra a composição atual do projeto sem mover, copiar, renomear, excluir ou reorganizar qualquer item.

## 2. Critérios de inclusão

Integram documentalmente a Baseline 1.0, quando existentes no workspace e não enquadrados nos critérios de exclusão:

- código-fonte;
- documentação;
- recursos;
- testes;
- scripts;
- workflows;
- ferramentas;
- arquivos de configuração;
- diretórios estruturais.

### 2.1 Inventário de arquivos integrantes por localização atual

Após aplicação dos critérios de exclusão da seção 3, foram identificados **494 arquivos preexistentes**. Com a incorporação deste manifesto, a Baseline 1.0 passa a registrar **495 arquivos integrantes**.

| Localização atual | Quantidade de arquivos integrantes | Classificação observada |
|---|---:|---|
| Raiz do projeto | 27 | Código-fonte, testes, scripts, configurações, especificações de empacotamento e documentos EP-001/EP-002 |
| `.vscode/` | 1 | Configuração do workspace |
| `assets/` | 1 | Recurso visual existente |
| `core/` | 184 | Código-fonte e testes atualmente contidos nessa árvore |
| `core_logic/` | 6 | Código-fonte |
| `docs/` | 1 | Documentação histórica existente |
| `executor/` | 7 | Código-fonte |
| `h_a/` | 73 | Código-fonte e testes atualmente contidos nessa árvore |
| `interface/` | 128 | Código-fonte da interface e integrações atualmente existentes |
| `legacy/` | 6 | Código-fonte existente classificado pela localização atual como legado |
| `policy/` | 2 | Código-fonte |
| `state/` | 5 | Código-fonte |
| `storage/` | 10 | Dados e documentos existentes de histórico, aprendizado e execução |
| `tests/` | 9 | Testes |
| `ui/` | 35 | Código-fonte e recursos da interface |
| **Total** | **495** | **494 artefatos preexistentes e este manifesto** |

### 2.2 Arquivos existentes na raiz

Integram o inventário atual da raiz:

- `.env`;
- `__init__.py`;
- `dummy_executor.py`;
- `EP-001_ESTRUTURA_REPOSITORIO_HANDA_CORE.md`;
- `EP-002_BASELINE_1_0_HANDA_CORE.md`;
- `erro.txt`;
- `HANDA.spec`;
- `iniciar_handa.bat`;
- `iniciar_handa_oculto.vbs`;
- `main.py`;
- `run_handa.py`;
- `run_handa.spec`;
- `run_live.py`;
- `run_ui.py`;
- `sell_btc.py`;
- `setup.py`;
- `slot_states.py`;
- `test_binance_connection.py`;
- `test_executor.py`;
- `test_executor_live.py`;
- `test_executor_mock.py`;
- `test_exit_cycle.py`;
- `test_market_engine.py`;
- `test_market_provider.py`;
- `test_slot_controller_isolated.py`;
- `test_slot_engine.py`;
- `test_ui_dummy.py`.

O registro de `.env` indica exclusivamente sua existência como arquivo de configuração no inventário atual. Não constitui autorização documental para publicação de conteúdo sensível.

### 2.3 Documentação existente

- `EP-001_ESTRUTURA_REPOSITORIO_HANDA_CORE.md`.
- `docs/historico_integrado/HISTORICO_HA_ALFRED_MARCO_ZERO.md`.
- Este documento, `EP-002_BASELINE_1_0_HANDA_CORE.md`, passa a registrar a composição da Baseline 1.0.

### 2.4 Recursos existentes

- `assets/icons/ha_icon.ico`.
- Recursos atualmente existentes dentro das árvores de código, conforme sua localização observada.

Os diretórios oficiais `resources/icons/`, `resources/images/` e `resources/themes/` encontram-se materializados e vazios. Nenhum recurso foi deslocado para esses diretórios.

### 2.5 Testes existentes

Foram identificados testes:

- na raiz, por meio dos arquivos prefixados por `test_`;
- em `tests/`, com nove arquivos;
- dentro das árvores `core/` e `h_a/`, conforme suas localizações atuais.

Nenhum teste foi movido ou reclassificado fisicamente.

### 2.6 Scripts existentes

Foram identificados scripts e comandos executáveis na raiz, incluindo arquivos `.py`, `.bat` e `.vbs`. O diretório oficial `scripts/` existe e permanece vazio.

### 2.7 Workflows e ferramentas

- O diretório estrutural `workflows/` existe e permanece vazio.
- O diretório estrutural `tools/` existe e permanece vazio.

Não foi localizado artefato de workflow ou ferramenta dentro desses diretórios oficiais.

### 2.8 Diretórios estruturais integrantes

Integram a Baseline como estrutura oficial materializada:

```text
docs/
├── architecture/
├── engineering/
├── governance/
├── audits/
├── knowledge/
└── decisions/

src/
└── handa_core/

tests/

resources/
├── icons/
├── images/
└── themes/

workflows/
scripts/
tools/

storage/
├── history/
├── learning/
└── runtime/
```

Além da estrutura oficial, permanecem integrantes do inventário os diretórios existentes que contêm os 495 arquivos relacionados na seção 2.1, preservados em suas localizações atuais.

## 3. Critérios de exclusão

Não integram a Baseline 1.0:

- ambientes virtuais, incluindo `.venv/`;
- caches, incluindo diretórios `__pycache__/` e caches equivalentes;
- arquivos compilados, incluindo `.pyc` e `.pyo`;
- diretórios de build, incluindo `build/`;
- diretórios de distribuição, incluindo `dist/`;
- logs e o diretório `logs/`;
- arquivos temporários;
- metadados gerados automaticamente, incluindo `h_a.egg-info/`;
- demais artefatos gerados automaticamente.

Esses itens foram somente classificados como excluídos. Nenhum deles foi removido ou alterado.

## 4. Estado da Baseline

- A estrutura oficial do repositório encontra-se materializada.
- Os artefatos permanecem preservados em sua localização atual.
- A publicação física no GitHub permanece pendente.
- Nenhuma reorganização estrutural foi iniciada.
- O diretório local não contém `.git` e, portanto, não foi identificado como repositório Git no workspace auditado.
- `README.md` não foi localizado.
- `.gitignore` não foi localizado.

## 5. Critérios para publicação

A publicação da Baseline somente poderá ocorrer após o atendimento cumulativo dos seguintes critérios:

| Critério | Evidência no inventário atual | Situação |
|---|---|---|
| Confirmação do Product Owner | Não localizada no inventário documental auditado | Pendente |
| Existência do README oficial | `README.md` não localizado | Pendente |
| Existência do `.gitignore` oficial | `.gitignore` não localizado | Pendente |
| Criação do repositório oficial | Diretório `.git` não localizado no workspace auditado | Pendente |
| Validação da composição da Baseline | Inventário consolidado neste documento; validação posterior não localizada | Pendente |

A elaboração deste documento não satisfaz automaticamente os critérios de confirmação, publicação ou validação posterior.

## 6. Classificação Final

**BASELINE 1.0 EM PREPARAÇÃO — NÃO PRONTA PARA PUBLICAÇÃO.**

A estrutura oficial está materializada e o inventário atual foi consolidado. Entretanto, os cinco critérios obrigatórios para publicação permanecem documentalmente pendentes.

## 7. Resumo Executivo

A Baseline 1.0 do H&A CORE registra 495 arquivos integrantes — 494 preexistentes e este manifesto — após a exclusão de ambientes virtuais, caches, compilados, build, dist, logs, temporários e metadados gerados automaticamente. A estrutura oficial possui 21 diretórios materializados; os artefatos permanecem em suas localizações atuais e nenhuma reorganização foi iniciada. A baseline ainda não está pronta para publicação porque não foram localizados README oficial, `.gitignore`, repositório Git local, confirmação do Product Owner ou validação posterior da composição.

## 8. Declaração de conformidade

Nenhum arquivo existente foi alterado, movido, copiado, renomeado ou removido. Nenhum código, arquitetura, documentação, configuração ou recurso existente foi modificado. O documento registra exclusivamente a composição oficial da Baseline 1.0 do H&A CORE. Nenhuma implementação foi iniciada e nenhuma atividade posterior foi executada.
