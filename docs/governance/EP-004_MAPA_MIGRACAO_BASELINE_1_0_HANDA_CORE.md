# EP-004 — MAPA OFICIAL DE MIGRAÇÃO DA BASELINE 1.0 H&A CORE

## 1. Objetivo

Registrar oficialmente o plano de migração física da Baseline 1.0 do H&A CORE, classificando o inventário diretorial existente, seus destinos oficiais e a estratégia aplicável a cada conjunto, sem iniciar movimentação, cópia, renomeação, exclusão ou consolidação física.

## 2. Critérios de classificação

Cada diretório ou conjunto estrutural recebe exclusivamente uma das classificações abaixo:

| Classificação | Significado |
|---|---|
| **Preservar** | Manter o item em sua localização atual porque ela já corresponde à estrutura oficial ou deve permanecer na raiz. |
| **Migrar** | Transferir futuramente o item para um destino oficial diferente, sem alteração automática de conteúdo. |
| **Consolidar** | Reunir futuramente o item com uma estrutura oficial ou conjunto equivalente, após validação de sobreposição e integridade. |
| **Arquivar** | Preservar futuramente o item como conteúdo histórico ou legado, separado dos componentes correntes. |
| **Excluir da Baseline** | Não publicar o item por corresponder a ambiente, cache, build, distribuição, log, temporário ou artefato gerado automaticamente. Não significa excluir fisicamente nesta atividade. |

As classificações definem estratégia documental. Nenhuma delas autoriza execução sem validação do Product Owner.

## 3. Inventário de migração

### 3.1 Diretórios existentes na raiz

| Diretório atual | Finalidade institucional observada | Classificação | Destino oficial | Justificativa |
|---|---|---|---|---|
| `.venv/` | Ambiente virtual Python local | Excluir da Baseline | Não aplicável | Ambiente de desenvolvimento excluído pela EP-002 e pelo `.gitignore`. |
| `.vscode/` | Configuração local do editor | Excluir da Baseline | Não aplicável | Ambiente de desenvolvimento excluído pelo `.gitignore`. |
| `assets/` | Recursos visuais atualmente existentes | Consolidar | `resources/` | A estrutura oficial concentra recursos em `resources/`. |
| `build/` | Artefatos de build | Excluir da Baseline | Não aplicável | Build excluído pela EP-002 e pelo `.gitignore`. |
| `core/` | Código-fonte do núcleo atualmente existente | Migrar | `src/handa_core/core/` | Código-fonte deve permanecer exclusivamente em `src/`. |
| `core_logic/` | Código-fonte de lógica atualmente existente | Migrar | `src/handa_core/core_logic/` | Código-fonte deve permanecer exclusivamente em `src/`. |
| `dist/` | Artefatos de distribuição | Excluir da Baseline | Não aplicável | Distribuição gerada excluída pela EP-002 e pelo `.gitignore`. |
| `docs/` | Documentação existente e estrutura documental oficial | Preservar | `docs/` | Já corresponde ao diretório oficial de documentação. |
| `executor/` | Código-fonte de execução atualmente existente | Consolidar | `src/handa_core/executor/` | Código-fonte deve migrar para `src/`; existem estruturas de execução em outras árvores que exigem validação antes da consolidação. |
| `h_a/` | Pacote de código-fonte atualmente existente | Consolidar | `src/handa_core/` | Deve integrar o diretório oficial do código do H&A CORE após validação de nomes e sobreposições. |
| `h_a.egg-info/` | Metadados gerados de distribuição | Excluir da Baseline | Não aplicável | Artefato gerado automaticamente e excluído pelo `.gitignore`. |
| `interface/` | Código-fonte de interface atualmente existente | Migrar | `src/handa_core/interface/` | Código-fonte deve permanecer exclusivamente em `src/`. |
| `legacy/` | Código-fonte identificado no inventário como legado | Arquivar | `src/handa_core/legacy/` | Deve ser preservado como código legado, separado dos componentes correntes. |
| `logs/` | Logs e históricos de execução | Excluir da Baseline | Não aplicável | Logs excluídos pela EP-002 e pelo `.gitignore`. |
| `policy/` | Código-fonte de políticas atualmente existente | Migrar | `src/handa_core/policy/` | Código-fonte deve permanecer exclusivamente em `src/`. |
| `resources/` | Estrutura oficial de recursos | Preservar | `resources/` | Já corresponde à estrutura oficial. |
| `scripts/` | Estrutura oficial de scripts | Preservar | `scripts/` | Já corresponde à estrutura oficial. |
| `src/` | Estrutura oficial de código-fonte | Preservar | `src/` | Já corresponde à estrutura oficial. |
| `state/` | Código-fonte de estado atualmente existente | Migrar | `src/handa_core/state/` | Código-fonte deve permanecer exclusivamente em `src/`. |
| `storage/` | Dados de histórico, aprendizado e runtime | Preservar | `storage/` | Já corresponde à estrutura oficial de dados de execução. |
| `tests/` | Estrutura oficial de testes | Preservar | `tests/` | Já corresponde à estrutura oficial. |
| `tools/` | Estrutura oficial de ferramentas | Preservar | `tools/` | Já corresponde à estrutura oficial. |
| `ui/` | Código-fonte e recursos de interface atualmente existentes | Migrar | `src/handa_core/ui/` | Código-fonte deve permanecer exclusivamente em `src/`; recursos internos dependem de validação durante a onda correspondente. |
| `workflows/` | Estrutura oficial de workflows | Preservar | `workflows/` | Já corresponde à estrutura oficial. |

### 3.2 Subdiretórios documentais existentes

| Diretório atual | Finalidade institucional | Classificação | Destino oficial | Justificativa |
|---|---|---|---|---|
| `docs/architecture/` | Documentos de Arquitetura | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `docs/engineering/` | Documentos de Engenharia | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `docs/governance/` | Documentos de Governança | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `docs/audits/` | Documentos de Auditoria | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `docs/knowledge/` | Base de Conhecimento | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `docs/decisions/` | Registros de decisões | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `docs/historico_integrado/` | Documentação histórica existente | Consolidar | `docs/knowledge/` | Não integra a árvore oficial da EP-001; o conteúdo é documentalmente identificado como histórico. |

### 3.3 Subdiretórios de recursos e código oficial

| Diretório atual | Finalidade institucional | Classificação | Destino oficial | Justificativa |
|---|---|---|---|---|
| `resources/icons/` | Ícones oficiais | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `resources/images/` | Imagens oficiais | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `resources/themes/` | Temas oficiais | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `src/handa_core/` | Código-fonte oficial do H&A CORE | Preservar | Mesmo diretório | Estrutura oficial já materializada. |

### 3.4 Subdiretórios de storage existentes

| Diretório atual | Finalidade institucional observada | Classificação | Destino oficial | Justificativa |
|---|---|---|---|---|
| `storage/history/` | Histórico de execução | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `storage/learning/` | Dados de aprendizado | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `storage/runtime/` | Dados de execução corrente | Preservar | Mesmo diretório | Estrutura oficial já materializada. |
| `storage/alo_profile/` | Perfis de aprendizado existentes | Consolidar | `storage/learning/` | Conteúdo localizado sob storage e identificado como perfil de aprendizado. |
| `storage/lc1/` | Eventos históricos existentes | Consolidar | `storage/history/` | Conteúdo observado em formato de histórico de eventos. |
| `storage/r_ia/` | Documentos existentes relacionados a aprendizado/IA | Consolidar | `storage/learning/` | Não integra a árvore oficial e permanece dentro do domínio de aprendizado. |

### 3.5 Regra para os demais subdiretórios

Os subdiretórios técnicos existentes dentro de `core/`, `core_logic/`, `executor/`, `h_a/`, `interface/`, `legacy/`, `policy/`, `state/`, `tests/` e `ui/` herdam a classificação e o destino do respectivo diretório-pai até a validação da onda de migração correspondente.

Subdiretórios `__pycache__/`, caches equivalentes e demais artefatos gerados automaticamente permanecem classificados como **Excluir da Baseline**, independentemente do diretório-pai.

### 3.6 Arquivos estruturais da raiz

| Arquivo ou conjunto atual | Finalidade institucional observada | Classificação | Destino oficial | Justificativa |
|---|---|---|---|---|
| `README.md` | Apresentação institucional | Preservar | Raiz | Documento inicial do repositório. |
| `.gitignore` | Controle de exclusões do Git | Preservar | Raiz | Configuração oficial de publicação. |
| `setup.py` | Configuração do pacote Python | Preservar | Raiz | Arquivo estrutural de configuração existente. |
| EP-001, EP-002, EP-003 e EP-004 | Documentação de estrutura, baseline e migração | Migrar | `docs/governance/` | Documentos de governança da estrutura e publicação. |
| `.env` | Variáveis locais | Excluir da Baseline | Não aplicável | Excluído pelo `.gitignore`. |
| `HANDA.spec` e `run_handa.spec` | Especificações PyInstaller | Excluir da Baseline | Não aplicável | Padrão `*.spec` excluído pelo `.gitignore`. |
| `erro.txt` | Registro de erro existente | Excluir da Baseline | Não aplicável | Corresponde a artefato de erro e não à estrutura oficial. |
| `__init__.py` | Código-fonte Python na raiz | Migrar | `src/handa_core/__init__.py` | Código-fonte deve permanecer exclusivamente em `src/`. |
| `dummy_executor.py` | Código-fonte de executor | Consolidar | `src/handa_core/executor/` | Deve ser validado junto às estruturas de execução existentes. |
| `slot_states.py` | Código-fonte de estado | Consolidar | `src/handa_core/state/` | Deve ser validado junto à estrutura de estado existente. |
| `main.py`, `run_handa.py`, `run_live.py` e `run_ui.py` | Pontos de execução existentes | Migrar | `scripts/` | Correspondem a scripts de inicialização/execução observados na raiz. |
| `sell_btc.py` | Script executável existente | Migrar | `scripts/` | Deve integrar o diretório oficial de scripts após validação. |
| `iniciar_handa.bat` e `iniciar_handa_oculto.vbs` | Scripts de inicialização | Migrar | `scripts/` | Devem integrar o diretório oficial de scripts. |
| Arquivos `test_*.py` da raiz | Testes existentes | Consolidar | `tests/` | Devem ser reunidos na estrutura oficial de testes após validação. |

Nenhum arquivo estrutural é movido, alterado ou renomeado por este mapa.

### 3.7 Consolidação quantitativa do mapa principal

| Escopo explicitamente classificado | Quantidade |
|---|---:|
| Diretórios existentes na raiz | 24 |
| Subdiretórios documentais | 7 |
| Subdiretórios de recursos e código oficial | 4 |
| Subdiretórios de storage | 6 |
| **Total de entradas diretoriais classificadas explicitamente** | **41** |

Os demais subdiretórios herdam a classificação conforme a seção 3.5 e serão inventariados individualmente somente na validação da onda que os abranger, sem mudança da classificação-pai por inferência.

## 4. Critérios de publicação

- Somente diretórios e artefatos classificados como integrantes da Baseline poderão ser publicados.
- Diretórios temporários, ambientes, caches, builds, distribuição, logs e artefatos gerados automaticamente permanecerão excluídos.
- Nenhuma migração ocorrerá sem validação do Product Owner.
- Itens classificados como Migrar, Consolidar ou Arquivar somente poderão ser executados após validação de conteúdo, destino e integridade.
- A existência de um destino neste mapa não autoriza movimentação automática.

## 5. Estratégia de execução

A migração será realizada em ondas organizadas por domínio funcional e documental, utilizando commits semânticos e preservando a rastreabilidade.

Cada onda deverá:

1. delimitar os diretórios e arquivos abrangidos;
2. validar a classificação e o destino contra este mapa;
3. verificar conflitos de nomes e sobreposição antes da execução;
4. preservar conteúdo e integridade;
5. excluir do conjunto de publicação os artefatos classificados como Excluir da Baseline;
6. registrar a mudança em commit semanticamente identificável;
7. validar o resultado antes da onda seguinte.

Este documento não define a execução concreta das ondas nem realiza commits.

## 6. Resultado esperado

Ao término da migração validada, a estrutura física do repositório deverá refletir integralmente a arquitetura oficial definida em `EP-001_ESTRUTURA_REPOSITORIO_HANDA_CORE.md`, preservando a composição da Baseline, a integridade dos artefatos e o histórico rastreável da evolução.

## 7. Resumo Executivo

O mapa classifica explicitamente 41 entradas diretoriais: 24 diretórios existentes na raiz, sete subdiretórios documentais, quatro subdiretórios de recursos/código oficial e seis subdiretórios de storage. Diretórios oficiais já compatíveis serão preservados; código disperso será migrado ou consolidado em `src/handa_core/`; recursos serão consolidados em `resources/`; testes em `tests/`; scripts em `scripts/`; itens históricos serão arquivados; ambientes, caches, build, dist, logs e gerados automaticamente permanecerão fora da Baseline. Nenhuma migração foi iniciada.

## 8. Declaração de conformidade

Nenhum arquivo, diretório, arquitetura, configuração, código, documentação ou recurso foi alterado, movido, copiado, renomeado ou removido. O documento registra exclusivamente o plano oficial de migração da Baseline 1.0 do H&A CORE. Nenhuma migração foi iniciada e nenhuma atividade posterior foi executada.
